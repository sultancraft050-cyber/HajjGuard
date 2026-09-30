import * as THREE from '../vendor-three.module.js';
import { OrbitControls } from '../vendor-orbit-controls.js';

const canvas = document.getElementById('hg-3d-canvas');
const fallbackPanel = document.getElementById('hg-fallback');
const zoneList = document.getElementById('hg-zone-list');
const stage = document.getElementById('hg-stage');
const zones = new Map();
let scene;
let camera;
let renderer;
let controls;
let raycaster;
let pointer;
let selected;
let frame;
let contentRoot;

function statusColor(status) {
    return { RED: 0xdc2626, ORANGE: 0xc47b00, GREEN: 0x475569 }[status] || 0x94a3b8;
}

function statusLabel(status) {
    return { RED: 'CRITICAL', ORANGE: 'BUSY', GREEN: 'COMFORTABLE' }[status] || 'NOT MEASURED';
}

function statusHex(status) {
    return statusColor(status);
}

function project(lat, lng) {
    const scale = 5200;
    return new THREE.Vector3((lng - 39.88) * scale, 0, -(lat - 21.40) * scale);
}

function addBox(parent, x, y, z, width, height, depth, color = 0xe5e7eb) {
    const mesh = new THREE.Mesh(
        new THREE.BoxGeometry(width, height, depth),
        new THREE.MeshStandardMaterial({ color, roughness: 0.82, metalness: 0.03 })
    );
    mesh.position.set(x, y, z);
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    parent.add(mesh);
    return mesh;
}

function addDome(parent, x, y, z, radius, height, color) {
    const dome = new THREE.Mesh(
        new THREE.ConeGeometry(radius, height, 24),
        new THREE.MeshStandardMaterial({ color, roughness: 0.9 })
    );
    dome.position.set(x, y, z);
    dome.rotation.y = Math.PI / 4;
    dome.castShadow = true;
    dome.receiveShadow = true;
    parent.add(dome);
    return dome;
}

function addHolySiteMasses(parent) {
    // Lightweight recognizable masses, intentionally labelled as a digital twin.
    const haram = new THREE.Group();
    haram.position.set(-250, 0, -110);
    parent.add(haram);
    const courtyard = new THREE.Mesh(
        new THREE.CylinderGeometry(105, 105, 5, 64),
        new THREE.MeshStandardMaterial({ color: 0xe5e7eb, roughness: 0.7 })
    );
    courtyard.position.y = 3;
    haram.add(courtyard);
    const kaaba = addBox(haram, 0, 16, 0, 27, 27, 27, 0x111827);
    kaaba.material.roughness = 0.55;
    const goldBand = addBox(haram, 0, 21, 13.8, 22, 3, 1, 0xc5a059);
    goldBand.material.metalness = 0.6;
    for (let i = 0; i < 8; i += 1) {
        const angle = (i / 8) * Math.PI * 2;
        const x = Math.cos(angle) * 122;
        const z = Math.sin(angle) * 122;
        const minaret = new THREE.Mesh(
            new THREE.CylinderGeometry(4, 6, 72, 16),
            new THREE.MeshStandardMaterial({ color: 0x6b7280, roughness: 0.7 })
        );
        minaret.position.set(x, 36, z);
        minaret.castShadow = true;
        haram.add(minaret);
        const cap = new THREE.Mesh(new THREE.SphereGeometry(7, 16, 8), new THREE.MeshStandardMaterial({ color: 0xc5a059, metalness: 0.5, roughness: 0.4 }));
        cap.scale.y = 0.55;
        cap.position.set(x, 74, z);
        haram.add(cap);
    }
    for (let i = 0; i < 14; i += 1) {
        const angle = (i / 14) * Math.PI * 2;
        const x = Math.cos(angle) * 165;
        const z = Math.sin(angle) * 165;
        addBox(haram, x, 16, z, 42, 32, 22, 0x9ca3af);
    }

    const mina = new THREE.Group();
    mina.position.set(330, 0, 35);
    parent.add(mina);
    for (let row = 0; row < 5; row += 1) {
        for (let col = 0; col < 10; col += 1) {
            addDome(mina, col * 20 - 90, 10, row * 18 - 36, 9, 15, row % 2 ? 0xdbe3ea : 0xcbd5e1);
        }
    }
    addBox(mina, 0, 3, 63, 230, 6, 7, 0x94a3b8);

    const jamarat = new THREE.Group();
    jamarat.position.set(400, 0, -170);
    parent.add(jamarat);
    [-35, 0, 35].forEach((x) => {
        addBox(jamarat, x, 20, 0, 16, 40, 48, 0x9ca3af);
        addBox(jamarat, x, 44, 0, 26, 6, 58, 0x475569);
        addBox(jamarat, x, 4, -34, 22, 8, 12, 0xcbd5e1);
    });
    addBox(jamarat, 0, 3, 52, 150, 6, 14, 0x64748b);

    const arafat = new THREE.Group();
    arafat.position.set(-80, 0, 320);
    parent.add(arafat);
    addBox(arafat, 0, 5, 0, 260, 10, 170, 0xd1d5db);
    addBox(arafat, 0, 25, -15, 36, 40, 36, 0x94a3b8);
    addBox(arafat, 0, 46, -15, 70, 8, 70, 0x64748b);
    for (let row = 0; row < 3; row += 1) {
        for (let col = 0; col < 8; col += 1) addDome(arafat, col * 28 - 98, 10, row * 30 + 22, 8, 13, 0xe2e8f0);
    }

    const muzdalifah = new THREE.Group();
    muzdalifah.position.set(170, 0, 230);
    parent.add(muzdalifah);
    addBox(muzdalifah, 0, 3, 0, 210, 6, 130, 0xe5e7eb);
    for (let row = 0; row < 3; row += 1) {
        for (let col = 0; col < 8; col += 1) addBox(muzdalifah, col * 24 - 84, 7, row * 30 - 35, 14, 8, 10, 0xcbd5e1);
    }
}

function buildScene(data) {
    scene = new THREE.Scene();
    scene.background = new THREE.Color(0xdfe5eb);
    scene.fog = new THREE.Fog(0xdfe5eb, 1050, 2200);
    camera = new THREE.PerspectiveCamera(42, 1, 1, 3000);
    camera.position.set(720, 580, 820);
    renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    controls = new OrbitControls(camera, canvas);
    controls.target.set(0, 0, 60);
    controls.enableDamping = true;
    controls.dampingFactor = 0.07;
    controls.minDistance = 240;
    controls.maxDistance = 1600;
    controls.maxPolarAngle = Math.PI * 0.48;
    raycaster = new THREE.Raycaster();
    pointer = new THREE.Vector2();

    scene.add(new THREE.HemisphereLight(0xffffff, 0x64748b, 2.1));
    const sun = new THREE.DirectionalLight(0xffffff, 2.4);
    sun.position.set(500, 900, 300);
    sun.castShadow = true;
    sun.shadow.mapSize.set(1024, 1024);
    scene.add(sun);
    const ground = new THREE.Mesh(
        new THREE.PlaneGeometry(1800, 1800),
        new THREE.MeshStandardMaterial({ color: 0xbcc6d1, roughness: 0.95 })
    );
    ground.rotation.x = -Math.PI / 2;
    ground.receiveShadow = true;
    scene.add(ground);
    const grid = new THREE.GridHelper(1800, 36, 0x64748b, 0xaeb9c5);
    grid.position.y = 1;
    scene.add(grid);

    contentRoot = new THREE.Group();
    scene.add(contentRoot);
    const masses = new THREE.Group();
    addHolySiteMasses(masses);
    contentRoot.add(masses);
    const zoneGroup = new THREE.Group();
    contentRoot.add(zoneGroup);
    const zoneMeshes = [];
    data.zones.forEach((zone) => {
        const p = project(zone.center_lat, zone.center_lng);
        const radius = Math.max(18, Math.min(70, zone.radius_meters / 1.8));
        const material = new THREE.MeshStandardMaterial({
            color: statusColor(zone.status),
            transparent: true,
            opacity: 0.35,
            roughness: 0.7,
            metalness: 0.05,
        });
        const mesh = new THREE.Mesh(new THREE.CylinderGeometry(radius, radius, 14, 40), material);
        mesh.position.set(p.x, 7, p.z);
        mesh.userData.zone = zone;
        zoneGroup.add(mesh);
        const ring = new THREE.Mesh(
            new THREE.RingGeometry(radius * 0.78, radius, 40),
            new THREE.MeshBasicMaterial({ color: statusHex(zone.status), transparent: true, opacity: 0.82, side: THREE.DoubleSide })
        );
        ring.rotation.x = -Math.PI / 2;
        ring.position.set(p.x, 15, p.z);
        ring.userData.zone = zone;
        zoneGroup.add(ring);
        const beacon = new THREE.Mesh(
            new THREE.CylinderGeometry(2.5, 2.5, 30, 12),
            new THREE.MeshStandardMaterial({ color: statusHex(zone.status), emissive: statusHex(zone.status), emissiveIntensity: 0.15 })
        );
        beacon.position.set(p.x, 22, p.z);
        beacon.castShadow = true;
        zoneGroup.add(beacon);
        zoneMeshes.push(mesh, ring);
        zones.set(zone.code, { zone, mesh });
    });
    data.corridors.forEach((corridor) => {
        const from = zones.get(corridor.from_zone)?.mesh?.position;
        const to = zones.get(corridor.to_zone)?.mesh?.position;
        if (!from || !to) return;
        const points = [new THREE.Vector3(from.x, 4, from.z), new THREE.Vector3(to.x, 4, to.z)];
        const geometry = new THREE.BufferGeometry().setFromPoints(points);
        const line = new THREE.Line(geometry, new THREE.LineBasicMaterial({ color: 0x64748b, transparent: true, opacity: 0.65 }));
        contentRoot.add(line);
    });
    stage.dataset.zoneMeshes = 'ready';
    canvas.addEventListener('pointerdown', () => { canvas.dataset.dragging = 'true'; });
    canvas.addEventListener('pointerup', () => { canvas.dataset.dragging = 'false'; });
    canvas.addEventListener('click', (event) => {
        const rect = canvas.getBoundingClientRect();
        pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
        pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
        raycaster.setFromCamera(pointer, camera);
        const hit = raycaster.intersectObjects(zoneMeshes, false)[0];
        if (hit?.object?.userData?.zone) selectZone(hit.object.userData.zone.code);
    });
    renderZoneList(data.zones);
    if (data.zones.length) selectZone(data.zones[0].code);
    resize();
    fitCameraToContent();
    animate();
}

function fitCameraToContent() {
    if (!contentRoot || !camera || !controls) return;
    const bounds = new THREE.Box3().setFromObject(contentRoot);
    const center = bounds.getCenter(new THREE.Vector3());
    const size = bounds.getSize(new THREE.Vector3());
    const span = Math.max(size.x, size.y, size.z, 500);
    const distance = Math.min(1550, Math.max(620, span * 1.08));
    controls.target.copy(center).setY(0);
    camera.position.set(center.x + distance * 0.78, distance * 0.66, center.z + distance * 0.82);
    camera.near = Math.max(0.5, distance / 2000);
    camera.far = Math.max(3000, distance * 4);
    camera.updateProjectionMatrix();
    controls.update();
}

function renderZoneList(items) {
    zoneList.classList.remove('visually-hidden');
    zoneList.className = 'hg-zone-list';
    zoneList.innerHTML = '<strong>Keyboard zone explorer</strong>';
    items.forEach((zone) => {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'hg-zone-list-item';
        button.textContent = zone.name_en;
        button.addEventListener('click', () => selectZone(zone.code));
        button.dataset.code = zone.code;
        zoneList.appendChild(button);
    });
}

function selectZone(code) {
    const entry = zones.get(code);
    if (!entry) return;
    if (selected) selected.mesh.material.emissive?.setHex(0x000000);
    selected = entry;
    if (selected.mesh.material.emissive) selected.mesh.material.emissive.setHex(0x334155);
    const zone = entry.zone;
    document.getElementById('hg-panel-title').textContent = zone.name_en;
    document.getElementById('hg-panel-sub').textContent = zone.name_ar;
    document.getElementById('hg-status').textContent = statusLabel(zone.status);
    document.getElementById('hg-density').textContent = zone.density_per_sqm == null ? 'Not measured' : `${zone.density_per_sqm} people/m²`;
    document.getElementById('hg-prediction').textContent = zone.predicted_density_20m == null ? 'Not measured' : `${zone.predicted_density_20m} people/m²`;
    document.getElementById('hg-risk').textContent = zone.risk_score == null ? 'Not measured' : `${zone.risk_score}/100`;
    document.querySelectorAll('.hg-zone-list-item').forEach((item) => item.setAttribute('aria-current', item.dataset.code === code ? 'true' : 'false'));
    if (controls && camera) {
        const target = selected.mesh.position.clone();
        target.y = 0;
        controls.target.lerp(target, 0.42);
        controls.update();
    }
}

function resize() {
    if (!renderer || !camera) return;
    const rect = canvas.getBoundingClientRect();
    renderer.setSize(rect.width, rect.height, false);
    camera.aspect = rect.width / Math.max(rect.height, 1);
    camera.updateProjectionMatrix();
}

function animate() {
    frame = requestAnimationFrame(animate);
    controls?.update();
    renderer?.render(scene, camera);
}

function showFallback() {
    fallbackPanel.hidden = false;
    canvas.hidden = true;
    zoneList.classList.remove('visually-hidden');
}

window.resetTwin = () => {
    fitCameraToContent();
};
window.fitTwin = () => {
    fitCameraToContent();
};
window.selectZone = selectZone;
window.addEventListener('resize', resize);

if (!canvas || !window.WebGLRenderingContext) {
    showFallback();
} else {
    fetch('/zones/api/digital-twin/', { credentials: 'same-origin' })
        .then((response) => { if (!response.ok) throw new Error('digital twin unavailable'); return response.json(); })
        .then(buildScene)
        .catch(() => showFallback());
}
