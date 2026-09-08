import networkx as nx
import numpy as np
from sklearn.linear_model import LinearRegression
from zones.models import Zone, Corridor, DensityRecord, LocationPing
from accounts.models import PilgrimProfile

class RoutingEngine:
    """
    NetworkX-powered dynamic congestion-aware pedestrian routing engine.
    Diverts pilgrim crowds away from saturated choke points.
    """

    @staticmethod
    def build_graph(congestion_penalty=True):
        G = nx.DiGraph()

        # Add Zones as nodes
        zones = {z.code: z for z in Zone.objects.all()}
        for code, zone in zones.items():
            rec = zone.density_records.first()
            current_people = rec.total_people if rec else 150
            ratio = current_people / max(zone.safe_capacity, 1)
            G.add_node(code, zone=zone, current_people=current_people, ratio=ratio)

        # Add Corridors as edges
        for corridor in Corridor.objects.filter(is_active=True):
            from_code = corridor.from_zone.code
            to_code = corridor.to_zone.code
            to_zone = corridor.to_zone
            
            # Base transit time in minutes
            cost = corridor.base_walking_minutes

            if congestion_penalty:
                # Add congestion factor based on destination zone utilization
                rec = to_zone.density_records.first()
                current_people = rec.total_people if rec else 150
                ratio = current_people / max(to_zone.safe_capacity, 1)

                if ratio >= 1.0: # Congested (RED)
                    cost *= (1.0 + (ratio * 4.0)) # Heavy penalty: 5x slower
                elif ratio >= 0.7: # Busy (AMBER)
                    cost *= (1.0 + (ratio * 1.5)) # Moderate penalty

            G.add_edge(
                from_code, 
                to_code, 
                weight=cost, 
                base_time=corridor.base_walking_minutes,
                corridor_name_en=corridor.name_en,
                corridor_name_ar=corridor.name_ar,
                width=corridor.width_meters
            )

        return G

    @classmethod
    def get_route_comparison(cls, from_zone_code, to_zone_code):
        """
        Runs route finding twice:
        1. Normal baseline (standard fastest path, no congestion awareness)
        2. HajjGuard congestion-aware path (avoids high-density bottlenecks)
        """
        # Baseline (standard map app)
        G_baseline = cls.build_graph(congestion_penalty=False)
        try:
            baseline_path = nx.shortest_path(G_baseline, from_zone_code, to_zone_code, weight='weight')
            baseline_time = nx.shortest_path_length(G_baseline, from_zone_code, to_zone_code, weight='weight')
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            baseline_path = [from_zone_code, to_zone_code]
            baseline_time = 25.0

        # Congestion-Aware
        G_congested = cls.build_graph(congestion_penalty=True)
        try:
            aware_path = nx.shortest_path(G_congested, from_zone_code, to_zone_code, weight='weight')
            aware_time = nx.shortest_path_length(G_congested, from_zone_code, to_zone_code, weight='weight')
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            aware_path = [from_zone_code, to_zone_code]
            aware_time = 20.0

        is_rerouted = (baseline_path != aware_path)

        # Check target zone status
        target_zone = Zone.objects.filter(code=to_zone_code).first()
        target_rec = target_zone.density_records.first() if target_zone else None
        target_is_congested = (target_rec and target_rec.status == 'RED')

        return {
            'from_zone': from_zone_code,
            'to_zone': to_zone_code,
            'is_rerouted': is_rerouted,
            'target_is_congested': target_is_congested,
            'baseline': {
                'path': baseline_path,
                'estimated_minutes': round(baseline_time, 1),
                'route_type': 'Standard Fastest Route'
            },
            'congestion_aware': {
                'path': aware_path,
                'estimated_minutes': round(aware_time, 1),
                'route_type': 'Dynamic Congestion Bypass Route' if is_rerouted else 'Optimal Direct Route',
                'reason': 'Direct route exceeds safe crowd density threshold. Diverted to alternate level/corridor.' if is_rerouted else 'All corridors operating within safe capacity limits.'
            }
        }

class PredictiveForecaster:
    """
    scikit-learn linear forecasting engine.
    Fits recent 1-hour trend (12 points at 5-min intervals) to predict density 20 mins ahead.
    """

    @staticmethod
    def forecast_zone(zone):
        records = list(zone.density_records.order_by('timestamp')[:12])
        if len(records) < 3:
            # Fallback projection if insufficient history
            current = zone.density_records.first()
            val = current.density_per_sqm if current else 0.5
            return round(val * 1.15, 2)

        # X is time steps (0, 1, 2, ... 11), y is density
        X = np.arange(len(records)).reshape(-1, 1)
        y = np.array([r.density_per_sqm for r in records])

        model = LinearRegression()
        model.fit(X, y)

        # Predict 4 steps ahead (+20 minutes)
        future_step = np.array([[len(records) + 4]])
        prediction = model.predict(future_step)[0]

        return max(0.0, round(float(prediction), 2))

class CrowdSimulator:
    """
    Simulates crowd movements, surges, and resets.
    """

    @staticmethod
    def trigger_jamarat_morning_surge():
        """
        Simulates morning stoning rush by surging 34,500 pilgrims into Jamarat Ground Floor (Z-JAMARAT-F0),
        crossing its 30,000 capacity limit into critical RED congestion.
        """
        jamarat_f0 = Zone.objects.filter(code='Z-JAMARAT-F0').first()
        if not jamarat_f0:
            return False

        # Set to congested RED (115% capacity)
        DensityRecord.objects.create(
            zone=jamarat_f0,
            phone_count=18000,
            image_count=16500,
            total_people=34500,
            density_per_sqm=2.88,
            predicted_density_20m=3.50,
            risk_score=88.5,
            status='RED'
        )

        # Set Jamarat 3rd floor as clear bypass option (30% capacity)
        jamarat_f3 = Zone.objects.filter(code='Z-JAMARAT-F3').first()
        if jamarat_f3:
            DensityRecord.objects.create(
                zone=jamarat_f3,
                phone_count=5000,
                image_count=4000,
                total_people=9000,
                density_per_sqm=0.75,
                predicted_density_20m=0.85,
                risk_score=22.0,
                status='GREEN'
            )

        return True

    @staticmethod
    def reset_all_zones_normal():
        """
        Resets all zones back to comfortable GREEN levels (20% to 35% safe capacity).
        """
        for zone in Zone.objects.all():
            normal_people = int(zone.safe_capacity * 0.25)
            density = normal_people / zone.floor_area_sqm
            DensityRecord.objects.create(
                zone=zone,
                phone_count=int(normal_people * 0.5),
                image_count=int(normal_people * 0.5),
                total_people=normal_people,
                density_per_sqm=round(density, 2),
                predicted_density_20m=round(density * 1.05, 2),
                risk_score=15.0,
                status='GREEN'
            )
        return True
