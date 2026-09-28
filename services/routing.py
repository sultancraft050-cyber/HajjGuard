import networkx as nx
from zones.models import Zone, Corridor
from zones.utils import haversine_distance

class RoutingEngine:
    """
    NetworkX-powered dynamic congestion-aware pedestrian routing engine.
    
    Architectural characteristics:
    - Uses a strictly Directed Graph (nx.DiGraph) to enforce one-way pilgrim corridors
      (e.g., Jamarat stoning entry-only routes, Masaa directional corridors).
    - Dynamically applies exponential congestion penalties to edge weights based on real-time
      destination density.
    - Resilient against disconnected subgraphs: returns graceful fallback detours instead of
      raising uncaught NetworkXNoPath or NodeNotFound exceptions.
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
            G.add_node(
                code,
                zone=zone,
                current_people=current_people,
                ratio=ratio,
                lat=zone.center_lat,
                lng=zone.center_lng,
                floor_level=zone.floor_level
            )

        # Add Active Corridors as directed edges
        for corridor in Corridor.objects.filter(is_active=True).select_related('from_zone', 'to_zone'):
            from_code = corridor.from_zone.code
            to_code = corridor.to_zone.code
            to_zone = corridor.to_zone

            # Base walking time in minutes
            cost = max(0.1, float(corridor.base_walking_minutes))

            if congestion_penalty:
                # Viscous Shockwave Dampened Cost Formulation:
                # W(e) = L_e * [1.0 + alpha * (rho_e / rho_jam)^beta] + delta_H * mu_incline
                rec = to_zone.density_records.first()
                current_people = rec.total_people if rec else 150
                floor_area = max(1.0, float(getattr(to_zone, 'floor_area_sqm', 1000)))
                density_sqm = current_people / floor_area
                safe_cap = max(to_zone.safe_capacity, 1)
                capacity_ratio = current_people / safe_cap

                rho_jam = 4.0   # Critical jam density in persons / sqm
                alpha = 3.0
                beta = 4.0

                shockwave_penalty = alpha * ((density_sqm / rho_jam) ** beta)

                if capacity_ratio >= 1.0:  # Congested (RED) - exponential barrier wall
                    cost *= (1.0 + (capacity_ratio * 4.0) + shockwave_penalty)
                elif capacity_ratio >= 0.7:  # Busy (ORANGE) - moderate resistance
                    cost *= (1.0 + (capacity_ratio * 1.5) + (shockwave_penalty * 0.5))

                # Vertical floor transition penalty (escalator/ramp incline queuing impedance)
                from_zone = corridor.from_zone
                floor_diff = abs(int(getattr(to_zone, 'floor_level', 0)) - int(getattr(from_zone, 'floor_level', 0)))
                cost += (floor_diff * 2.5)  # 2.5 minutes per vertical level transition

            G.add_edge(
                from_code,
                to_code,
                weight=round(cost, 2),
                base_time=corridor.base_walking_minutes,
                corridor_name_en=corridor.name_en,
                corridor_name_ar=corridor.name_ar,
                width=corridor.width_meters
            )

        return G

    @classmethod
    def find_path_safe(cls, G, from_zone_code, to_zone_code):
        """
        Safely computes shortest path. If nodes do not exist or graph is disconnected,
        returns fallback without raising NetworkXNoPath or NodeNotFound.
        """
        if from_zone_code not in G or to_zone_code not in G:
            return {
                'path': [from_zone_code, to_zone_code],
                'estimated_minutes': 25.0,
                'is_connected': False,
                'error': 'One or both zones not found in active routing graph'
            }

        try:
            if not nx.has_path(G, from_zone_code, to_zone_code):
                # Calculate approximate straight-line walking time as fallback
                from_node = G.nodes[from_zone_code]
                to_node = G.nodes[to_zone_code]
                dist_m = haversine_distance(from_node['lat'], from_node['lng'], to_node['lat'], to_node['lng'])
                # Average walking speed ~1.0 m/s => 60 meters per minute
                est_minutes = max(5.0, round(dist_m / 60.0, 1))

                return {
                    'path': [from_zone_code, to_zone_code],
                    'estimated_minutes': est_minutes,
                    'is_connected': False,
                    'error': 'No active corridor path connects these zones directly'
                }

            path = nx.shortest_path(G, from_zone_code, to_zone_code, weight='weight')
            time_mins = nx.shortest_path_length(G, from_zone_code, to_zone_code, weight='weight')

            return {
                'path': path,
                'estimated_minutes': round(float(time_mins), 1),
                'is_connected': True,
                'error': None
            }
        except (nx.NetworkXNoPath, nx.NodeNotFound, KeyError) as e:
            return {
                'path': [from_zone_code, to_zone_code],
                'estimated_minutes': 25.0,
                'is_connected': False,
                'error': str(e)
            }

    @classmethod
    def get_route_comparison(cls, from_zone_code, to_zone_code):
        """
        Runs dual-pass route evaluation:
        1. Baseline (standard map shortest path, unaware of crowd density).
        2. HajjGuard Congestion-Aware path (diverts away from saturated choke points).
        """
        G_baseline = cls.build_graph(congestion_penalty=False)
        baseline_res = cls.find_path_safe(G_baseline, from_zone_code, to_zone_code)

        G_aware = cls.build_graph(congestion_penalty=True)
        aware_res = cls.find_path_safe(G_aware, from_zone_code, to_zone_code)

        # Check target zone congestion status
        target_zone = Zone.objects.filter(code=to_zone_code).first()
        target_rec = target_zone.density_records.first() if target_zone else None
        target_is_congested = (target_rec and target_rec.status == 'RED')

        # If destination zone is congested (e.g. Jamarat Ground Floor, Mataf Basin), evaluate safe alternate floors in the same complex
        if target_is_congested and target_zone:
            alternate_zones = Zone.objects.filter(site_type=target_zone.site_type).exclude(code__in=[to_zone_code, from_zone_code])
            best_alternate_res = None
            best_alternate_cost = aware_res['estimated_minutes']

            for alt_z in alternate_zones:
                alt_rec = alt_z.density_records.first()
                if not alt_rec or alt_rec.status != 'RED':
                    candidate_res = cls.find_path_safe(G_aware, from_zone_code, alt_z.code)
                    if candidate_res['is_connected'] and len(candidate_res['path']) > 1 and candidate_res['estimated_minutes'] < best_alternate_cost:
                        best_alternate_cost = candidate_res['estimated_minutes']
                        best_alternate_res = candidate_res

            if best_alternate_res:
                aware_res = best_alternate_res

        is_rerouted = (baseline_res['path'] != aware_res['path'])

        if not aware_res['is_connected']:
            reason = 'Disconnected path: no direct one-way pedestrian corridor currently open between these zones.'
            route_type = 'Disconnected Path (Direct Vector Fallback)'
        elif is_rerouted:
            reason = 'Direct route exceeds safe crowd density threshold. Diverted to alternate level or bypass corridor.'
            route_type = 'Dynamic Congestion Bypass Route'
        else:
            reason = 'All corridors operating within safe capacity limits.'
            route_type = 'Optimal Direct Route'

        return {
            'from_zone': from_zone_code,
            'to_zone': to_zone_code,
            'is_rerouted': is_rerouted,
            'target_is_congested': target_is_congested,
            'is_connected': aware_res['is_connected'],
            'baseline': {
                'path': baseline_res['path'],
                'estimated_minutes': baseline_res['estimated_minutes'],
                'route_type': 'Standard Fastest Route',
                'is_connected': baseline_res['is_connected']
            },
            'congestion_aware': {
                'path': aware_res['path'],
                'estimated_minutes': aware_res['estimated_minutes'],
                'route_type': route_type,
                'reason': reason,
                'is_connected': aware_res['is_connected']
            }
        }

    @classmethod
    def find_k_shortest_paths_stochastic(cls, G, from_zone_code, to_zone_code, k=3, theta=0.8):
        """
        Computes top-k loopless paths and assigns stochastic logit assignment probabilities:
        P(Path_i) = exp(-theta * W_i) / sum_j exp(-theta * W_j)
        
        Diffuses mass pedestrian waves across parallel corridors to prevent secondary shockwaves.
        """
        import math
        import itertools

        if from_zone_code not in G or to_zone_code not in G:
            return []

        try:
            generator = nx.shortest_simple_paths(G, from_zone_code, to_zone_code, weight='weight')
            raw_paths = list(itertools.islice(generator, k))
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return []

        if not raw_paths:
            return []

        candidates = []
        for path in raw_paths:
            total_cost = 0.0
            for u, v in zip(path[:-1], path[1:]):
                total_cost += G[u][v].get('weight', 1.0)
            candidates.append({
                'path': path,
                'cost_minutes': round(float(total_cost), 1),
                'exp_weight': math.exp(-theta * min(50.0, float(total_cost)))
            })

        sum_exp = sum(c['exp_weight'] for c in candidates) or 1.0
        for c in candidates:
            c['assignment_probability'] = round(c['exp_weight'] / sum_exp, 3)
            del c['exp_weight']

        return candidates

