import * as THREE from '../vendor-three.module.js';

// Architectural illustration in relative units; not a surveyed mosque model.
export function buildHaramArchitecture() {
    const root = new THREE.Group();
    root.name = 'Haram architectural illustration';
    const marble = new THREE.MeshStandardMaterial({color: 0xf4f2ee, roughness: .76});
    const stone = new THREE.MeshStandardMaterial({color: 0xd8d5cf, roughness: .86});
    const gold = new THREE.MeshStandardMaterial({color: 0xbba16a, metalness: .65, roughness: .4});
    const black = new THREE.MeshStandardMaterial({color: 0x171717, roughness: .94});
    function mesh(geometry, material, x, y, z, name) {
        const m = new THREE.Mesh(geometry, material);
        m.position.set(x, y, z); m.name = name;
        m.castShadow = true; m.receiveShadow = true; root.add(m); return m;
    }
    function box(x,y,z,w,h,d,material,name) {
        return mesh(new THREE.BoxGeometry(w,h,d),material,x,y,z,name);
    }
    box(0,1,0,320,2,280,marble,'Marble courtyard');
    // Subtle flush paving joints, instead of floating circular rings.
    const joints = new THREE.BufferGeometry();
    const vertices = [];
    for(let i=-140;i<=140;i+=14) vertices.push(i,2.03,-125,i,2.03,125);
    for(let i=-125;i<=125;i+=14) vertices.push(-140,2.03,i,140,2.03,i);
    joints.setAttribute('position',new THREE.Float32BufferAttribute(vertices,3));
    const paving = new THREE.LineSegments(joints,new THREE.LineBasicMaterial({color:0xd8d5d0,transparent:true,opacity:.4}));
    root.add(paving);
    box(0,3,0,30,2,27,stone,'Kaaba marble base');
    box(0,17,0,27,26,24,black,'Kaaba');
    box(0,24,12.08,27,2,.18,gold,'Kiswa front band');
    box(0,24,-12.08,27,2,.18,gold,'Kiswa back band');
    box(13.58,24,0,.18,2,24,gold,'Kiswa side band');
    box(-13.58,24,0,.18,2,24,gold,'Kiswa side band');
    box(5,13,12.2,4.5,8,.3,gold,'Raised Kaaba door');
    for(const x of [-9,-3,3,9]) box(x,19,12.17,1.5,2,.22,gold,'Decorative cloth panel');
    const hijr = mesh(new THREE.CylinderGeometry(21,21,3,48,1,true,Math.PI*.1,Math.PI*.8),marble,0,3.5,-15,'Hijr semicircular wall');
    hijr.material = marble.clone(); hijr.material.side = THREE.DoubleSide;
    // Repeated open arch bays have a real opening, with two stacked galleries.
    const arch = new THREE.Shape();
    arch.moveTo(-7,0); arch.lineTo(-7,17); arch.lineTo(7,17); arch.lineTo(7,0);
    arch.lineTo(4.8,0); arch.lineTo(4.8,8);
    arch.absarc(0,8,4.8,0,Math.PI,false);
    arch.lineTo(-4.8,0); arch.lineTo(-7,0);
    const archGeometry = new THREE.ExtrudeGeometry(arch,{depth:2,bevelEnabled:false,curveSegments:12});
    const bayTransforms=[];
    for(let x=-126;x<=126;x+=14) for(const z of [-112,112]) bayTransforms.push([x,z,z>0?Math.PI:0]);
    for(let z=-98;z<=98;z+=14) for(const x of [-140,140]) bayTransforms.push([x,z,x>0?-Math.PI/2:Math.PI/2]);
    const arcade=new THREE.InstancedMesh(archGeometry,stone,bayTransforms.length*2);
    arcade.name='Open two-storey arcades'; arcade.castShadow=true; arcade.receiveShadow=true;
    const transform=new THREE.Object3D(); let index=0;
    for(const [x,z,rotation] of bayTransforms) for(const y of [2,20]) {
        transform.position.set(x,y,z); transform.rotation.set(0,rotation,0); transform.updateMatrix();
        arcade.setMatrixAt(index++,transform.matrix);
    }
    root.add(arcade);
    for(const z of [-124,124]) {
        box(0,20,z,294,2,26,marble,'Gallery floor');
        box(0,38,z,294,2,26,marble,'Gallery roof');
        box(0,39.7,z+(z>0?12:-12),294,1.4,1.2,stone,'Roof parapet');
    }
    for(const x of [-152,152]) {
        box(x,20,0,26,2,250,marble,'Gallery floor');
        box(x,38,0,26,2,250,marble,'Gallery roof');
    }
    // Small roof domes rather than one oversized torus.
    const domeGeometry=new THREE.SphereGeometry(6,16,10,0,Math.PI*2,0,Math.PI/2);
    for(let x=-112;x<=112;x+=28) for(const z of [-124,124]) mesh(domeGeometry,marble,x,39,z,'Gallery roof dome');
    for(const x of [-150,150]) for(const z of [-112,0,112]) {
        mesh(new THREE.CylinderGeometry(5,6,46,16),marble,x,61,z,'Minaret shaft');
        for(const y of [47,69,83]) mesh(new THREE.CylinderGeometry(7,7,2,16),stone,x,y,z,'Minaret balcony');
        mesh(new THREE.CylinderGeometry(3,4,18,16),marble,x,92,z,'Minaret lantern');
        mesh(new THREE.ConeGeometry(4,9,16),stone,x,105,z,'Minaret crown');
        mesh(new THREE.SphereGeometry(1.1,8,8),gold,x,111,z,'Minaret finial');
    }
    return root;
}
