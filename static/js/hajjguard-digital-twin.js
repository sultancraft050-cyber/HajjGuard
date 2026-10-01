import * as THREE from '../vendor-three.module.js';
import { OrbitControls } from '../vendor-orbit-controls.js';
import { buildHaramArchitecture } from './haram-geometry.js';

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
let hovered;
let frame;
let contentRoot;
let walkMode = false;
const siteGroups = new Map();

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

function addSiteLabel(parent, text, x, y, z) {
    const labelCanvas = document.createElement('canvas');
    labelCanvas.width = 512;
    labelCanvas.height = 96;
    const context = labelCanvas.getContext('2d');
    context.fillStyle = 'rgba(15, 23, 42, 0.88)';
    if (typeof context.roundRect === 'function') context.roundRect(4, 4, 504, 88, 18);
    else context.rect(4, 4, 504, 88);
    context.fill();
    context.font = '700 34px Arial, sans-serif';
    context.fillStyle = '#ffffff';
    context.textAlign = 'center';
    context.textBaseline = 'middle';
    context.fillText(text, 256, 48);
    const texture = new THREE.CanvasTexture(labelCanvas);
    texture.colorSpace = THREE.SRGBColorSpace;
    const sprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: texture, transparent: true, depthTest: false }));
    sprite.position.set(x, y, z);
    sprite.scale.set(120, 22.5, 1);
    parent.add(sprite);
    return sprite;
}

function addMinaret(parent, x, z) {
    const base = new THREE.Mesh(new THREE.CylinderGeometry(9, 11, 12, 20), new THREE.MeshStandardMaterial({ color: 0x9ca3af, roughness: 0.8 }));
    base.position.set(x, 6, z);
    base.castShadow = true;
    parent.add(base);
    const shaft = new THREE.Mesh(new THREE.CylinderGeometry(4, 5.5, 52, 20), new THREE.MeshStandardMaterial({ color: 0x64748b, roughness: 0.7 }));
    shaft.position.set(x, 38, z);
    shaft.castShadow = true;
    parent.add(shaft);
    const balcony = new THREE.Mesh(new THREE.CylinderGeometry(8, 8, 4, 20), new THREE.MeshStandardMaterial({ color: 0x94a3b8, roughness: 0.65 }));
    balcony.position.set(x, 61, z);
    balcony.castShadow = true;
    parent.add(balcony);
    const upper = new THREE.Mesh(new THREE.CylinderGeometry(3, 3.8, 14, 20), new THREE.MeshStandardMaterial({ color: 0x64748b, roughness: 0.7 }));
    upper.position.set(x, 70, z);
    upper.castShadow = true;
    parent.add(upper);
    const cap = new THREE.Mesh(new THREE.ConeGeometry(7, 10, 20), new THREE.MeshStandardMaterial({ color: 0xc5a059, metalness: 0.55, roughness: 0.4 }));
    cap.position.set(x, 82, z);
    cap.castShadow = true;
    parent.add(cap);
}

function addHolySiteMasses(parent) {
    // Lightweight recognizable masses, intentionally labelled as a digital twin.
    const haram = new THREE.Group();
    haram.position.set(-280, 0, -117);
    parent.add(haram);
    siteGroups.set('haram', haram);
    haram.add(buildHaramArchitecture());
    addSiteLabel(haram, 'Masjid al-Haram', 0, 104, 0);
    const sai = new THREE.Group();
    sai.position.set(0, 0, 235);
    haram.add(sai);
    addBox(sai, 0, 14, 0, 230, 28, 42, 0xb6c0cb);
    addBox(sai, 0, 30, 0, 210, 4, 36, 0xe5e7eb);
    for (let i = 0; i < 9; i += 1) {
        addBox(sai, i * 24 - 96, 20, -18, 5, 18, 5, 0x64748b);
        addBox(sai, i * 24 - 96, 20, 18, 5, 18, 5, 0x64748b);
    }
    addSiteLabel(sai, 'Sa’i corridor', 0, 54, 0);

    const mina = new THREE.Group();
    mina.position.set(88, 0, -73);
    parent.add(mina);
    siteGroups.set('mina', mina);
    for (let row = 0; row < 5; row += 1) {
        for (let col = 0; col < 10; col += 1) {
            addDome(mina, col * 20 - 90, 10, row * 18 - 36, 9, 15, row % 2 ? 0xdbe3ea : 0xcbd5e1);
        }
    }
    addBox(mina, 0, 3, 63, 230, 6, 7, 0x94a3b8);
    addSiteLabel(mina, 'Mina', 0, 46, 70);

    const jamarat = new THREE.Group();
    jamarat.position.set(-44, 0, -103);
    parent.add(jamarat);
    siteGroups.set('jamarat', jamarat);
    [-35, 0, 35].forEach((x) => {
        addBox(jamarat, x, 20, 0, 16, 40, 48, 0x9ca3af);
        addBox(jamarat, x, 44, 0, 26, 6, 58, 0x475569);
        addBox(jamarat, x, 4, -34, 22, 8, 12, 0xcbd5e1);
    });
    addBox(jamarat, 0, 3, 52, 150, 6, 14, 0x64748b);
    addSiteLabel(jamarat, 'Jamarat', 0, 80, 20);

    const arafat = new THREE.Group();
    arafat.position.set(541, 0, 235);
    parent.add(arafat);
    siteGroups.set('arafat', arafat);
    addBox(arafat, 0, 5, 0, 260, 10, 170, 0xd1d5db);
    addBox(arafat, 0, 25, -15, 36, 40, 36, 0x94a3b8);
    addBox(arafat, 0, 46, -15, 70, 8, 70, 0x64748b);
    addBox(arafat, 0, 58, -15, 46, 8, 46, 0x475569);
    addBox(arafat, 0, 69, -15, 22, 10, 22, 0x334155);
    for (let row = 0; row < 3; row += 1) {
        for (let col = 0; col < 8; col += 1) addDome(arafat, col * 28 - 98, 10, row * 30 + 22, 8, 13, 0xe2e8f0);
    }
    addSiteLabel(arafat, 'Arafat', 0, 72, 0);

    const muzdalifah = new THREE.Group();
    muzdalifah.position.set(140, 0, 47);
    parent.add(muzdalifah);
    siteGroups.set('muzdalifah', muzdalifah);
    addBox(muzdalifah, 0, 3, 0, 210, 6, 130, 0xe5e7eb);
    for (let row = 0; row < 3; row += 1) {
        for (let col = 0; col < 8; col += 1) addBox(muzdalifah, col * 24 - 84, 7, row * 30 - 35, 14, 8, 10, 0xcbd5e1);
    }
    addSiteLabel(muzdalifah, 'Muzdalifah', 0, 42, 0);
}

function buildScene(data) {
    siteGroups.clear();
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
    controls.enableDamping = !window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    controls.dampingFactor = 0.07;
    controls.minDistance = 45;
    controls.maxDistance = 1600;
    controls.maxPolarAngle = Math.PI * 0.48;
    controls.addEventListener('change', syncCameraState);
    raycaster = new THREE.Raycaster();
    pointer = new THREE.Vector2();

    scene.add(new THREE.HemisphereLight(0xffffff, 0x64748b, 2.1));
    const sun = new THREE.DirectionalLight(0xffffff, 2.4);
    sun.position.set(500, 900, 300);
    sun.castShadow = true;
    sun.shadow.mapSize.set(2048, 2048);
    Object.assign(sun.shadow.camera, {left: -950, right: 950, top: 950, bottom: -950, near: 1, far: 2400});
    sun.shadow.bias = -0.0004;
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
        const points = [new THREE.Vector3(from.x, 5, from.z), new THREE.Vector3(to.x, 5, to.z)];
        const curve = new THREE.LineCurve3(points[0], points[1]);
        const corridorWidth = Number(corridor.width_meters) || 6;
        const geometry = new THREE.TubeGeometry(curve, 12, Math.max(2.5, Math.min(8, corridorWidth / 2)), 8, false);
        const road = new THREE.Mesh(geometry, new THREE.MeshStandardMaterial({ color: 0x475569, roughness: 0.9, transparent: true, opacity: 0.82 }));
        road.receiveShadow = true;
        contentRoot.add(road);
    });
    stage.dataset.zoneMeshes = 'ready';
    let dragStart;
    let moved = false;
    canvas.addEventListener('pointerdown', (event) => {
        canvas.focus(); dragStart = [event.clientX, event.clientY]; moved = false; canvas.dataset.dragging = 'true';
    });
    canvas.addEventListener('pointercancel', () => { moved = true; canvas.dataset.dragging = 'false'; });
    canvas.addEventListener('pointerup', () => { canvas.dataset.dragging = 'false'; });
    canvas.addEventListener('pointermove', (event) => {
        if (canvas.dataset.dragging === 'true' && dragStart && Math.hypot(event.clientX - dragStart[0], event.clientY - dragStart[1]) > 6) moved = true;
        const rect = canvas.getBoundingClientRect();
        pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
        pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
        raycaster.setFromCamera(pointer, camera);
        const hit = raycaster.intersectObjects(zoneMeshes, false)[0]?.object;
        if (hovered && hovered !== hit && hovered !== selected?.mesh) hovered.material.emissive?.setHex(0x000000);
        hovered = hit || null;
        if (hovered && hovered !== selected?.mesh) hovered.material.emissive?.setHex(0x334155);
        canvas.style.cursor = hovered ? 'pointer' : (canvas.dataset.dragging === 'true' ? 'grabbing' : 'grab');
    });
    canvas.addEventListener('pointerleave', () => {
        if (hovered && hovered !== selected?.mesh) hovered.material.emissive?.setHex(0x000000);
        hovered = null;
        canvas.style.cursor = 'grab';
    });
    canvas.addEventListener('keydown', (event) => {
        if (!walkMode) return;
        const key = event.key.toLowerCase();
        if (!['w', 'a', 's', 'd', 'arrowup', 'arrowdown', 'arrowleft', 'arrowright'].includes(key)) return;
        event.preventDefault();
        const direction = new THREE.Vector3();
        camera.getWorldDirection(direction);
        direction.y = 0;
        direction.normalize();
        const right = new THREE.Vector3(-direction.z, 0, direction.x);
        const step = event.shiftKey ? 34 : 16;
        const movement = new THREE.Vector3();
        if (key === 'w' || key === 'arrowup') movement.addScaledVector(direction, step);
        if (key === 's' || key === 'arrowdown') movement.addScaledVector(direction, -step);
        if (key === 'a' || key === 'arrowleft') movement.addScaledVector(right, -step);
        if (key === 'd' || key === 'arrowright') movement.addScaledVector(right, step);
        camera.position.add(movement);
        controls.target.add(movement);
        controls.update();
    });
    canvas.addEventListener('click', (event) => {
        if (moved) return;
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
    focusSite('haram');
    animate();
}

function syncCameraState() {
    if (!stage || !camera) return;
    stage.dataset.camera = [camera.position.x, camera.position.y, camera.position.z, controls?.target.x, controls?.target.z]
        .map((value) => Number(value || 0).toFixed(1)).join(',');
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
    syncCameraState();
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
    if (selected?.mesh) selected.mesh.material.emissive?.setHex(0x000000);
    selected = entry;
    if (selected.mesh?.material.emissive) selected.mesh.material.emissive.setHex(0x334155);
    const zone = entry.zone;
    document.getElementById('hg-panel-title').textContent = zone.name_en;
    document.getElementById('hg-panel-sub').textContent = zone.name_ar;
    document.getElementById('hg-status').textContent = statusLabel(zone.status);
    document.getElementById('hg-density').textContent = zone.density_per_sqm == null ? 'Not measured' : `${zone.density_per_sqm} people/m²`;
    document.getElementById('hg-prediction').textContent = zone.predicted_density_20m == null ? 'Not measured' : `${zone.predicted_density_20m} people/m²`;
    document.getElementById('hg-risk').textContent = zone.risk_score == null ? 'Not measured' : `${zone.risk_score}/100`;
    document.querySelectorAll('.hg-zone-list-item').forEach((item) => item.setAttribute('aria-current', item.dataset.code === code ? 'true' : 'false'));
    if (controls && camera && selected.mesh) {
        const target = selected.mesh.position.clone();
        target.y = 0;
        controls.target.lerp(target, 0.42);
        controls.update();
    }
}

function focusSite(siteKey) {
    const group = siteGroups.get(siteKey);
    if (!group || !camera || !controls) return;
    const bounds = new THREE.Box3().setFromObject(group);
    const center = bounds.getCenter(new THREE.Vector3());
    const size = bounds.getSize(new THREE.Vector3());
    const distance = Math.max(230, Math.max(size.x, size.z) * 1.1 / Math.tan(THREE.MathUtils.degToRad(camera.fov / 2)));
    controls.target.copy(center).setY(0);
    camera.position.set(center.x + distance * 0.8, distance * 0.65, center.z + distance * 0.8);
    controls.update();
}

function resize() {
    if (!renderer || !camera) return;
    const rect = canvas.getBoundingClientRect();
    renderer.setSize(rect.width, rect.height, false);
    camera.aspect = rect.width / Math.max(rect.height, 1);
    camera.updateProjectionMatrix();
}

function animate() {
    if (document.hidden) { frame = null; return; }
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
window.toggleTwinExpanded = () => {
    if (!stage) return;
    const expanded = stage.classList.toggle('is-expanded');
    document.body.classList.toggle('hg-twin-open', expanded);
    const button = document.getElementById('hg-expand-button');
    if (button) {
        button.setAttribute('aria-label', expanded ? 'Close expanded model' : 'Expand model');
        button.title = expanded ? 'Close expanded model' : 'Expand model';
    }
    resize();
};
window.toggleWalkMode = () => {
    walkMode = !walkMode;
    const button = document.getElementById('hg-walk-button');
    if (button) {
        button.setAttribute('aria-label', walkMode ? 'Disable walkthrough mode' : 'Enable walkthrough mode');
        button.title = walkMode ? 'Walkthrough mode enabled: use W A S D or arrow keys' : 'Enable walkthrough mode';
        button.classList.toggle('is-active', walkMode);
    }
    if (walkMode) canvas?.focus();
};
window.toggleTwinDetails = () => {
    const panel = document.getElementById('hg-panel');
    const button = document.getElementById('hg-details-button');
    if (!panel || !button) return;
    const hidden = panel.classList.toggle('is-hidden');
    button.setAttribute('aria-label', hidden ? 'Show details panel' : 'Hide details panel');
    button.title = hidden ? 'Show details panel' : 'Hide details panel';
};
window.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && stage?.classList.contains('is-expanded')) window.toggleTwinExpanded();
});
window.selectZone = selectZone;
window.focusSite = focusSite;
window.addEventListener('resize', resize);
document.addEventListener('visibilitychange', () => { if (!document.hidden && renderer && !frame) animate(); });
new ResizeObserver(resize).observe(stage);

if (canvas) {
    fetch('/zones/api/digital-twin/', { credentials: 'same-origin' })
        .then((response) => { if (!response.ok) throw new Error('digital twin unavailable'); return response.json(); })
        .then((data) => {
            // Keep inspection usable even when this device cannot create a WebGL context.
            data.zones.forEach((zone) => zones.set(zone.code, { zone }));
            renderZoneList(data.zones);
            if (!window.WebGLRenderingContext) {
                showFallback();
                if (data.zones.length) selectZone(data.zones[0].code);
                return;
            }
            try { buildScene(data); }
            catch (error) {
                showFallback();
                if (data.zones.length) selectZone(data.zones[0].code);
            }
        })
        .catch(() => showFallback());
}
