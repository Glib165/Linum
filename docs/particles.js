// Хмара частинок у формі іконки Linum (Крик), яку ворушить курсор.
//
// Як це працює:
// 1. Кожна частинка має "своє місце" на білих лініях іконки (маска з linum-mask.js).
// 2. Положення всіх частинок зберігаються в текстурі на відеокарті. Щокадру один шейдер
//    підтягує кожну частинку до її місця, додає легке "дихання" і поштовх від курсора.
// 3. Курсор розмішує невелику симуляцію рідини. Де рідина рухається, туди її течія
//    і зносить частинки, а потім вони повертаються на місце.

(function () {
    "use strict";

    const canvas = document.getElementById("bg");
    if (!window.THREE || !window.LINUM_MASK) {
        document.body.classList.add("no-webgl");
        return;
    }

    let renderer;
    try {
        renderer = new THREE.WebGLRenderer({ canvas: canvas, antialias: false, powerPreference: "high-performance" });
    } catch (error) {
        document.body.classList.add("no-webgl");
        return;
    }
    if (!renderer.capabilities.isWebGL2 || !renderer.extensions.get("EXT_color_buffer_float")) {
        document.body.classList.add("no-webgl");
        return;
    }

    const MOBILE = window.matchMedia("(max-width: 760px), (pointer: coarse)").matches;
    const DPR = Math.min(window.devicePixelRatio || 1, 2);
    const TEX = MOBILE ? 128 : 256;          // частинок: TEX × TEX
    const COUNT = TEX * TEX;
    const SIM = MOBILE ? 128 : 256;          // роздільність симуляції рідини
    const DYE = MOBILE ? 256 : 512;          // роздільність "фарби", яка показує, де пройшов курсор
    const ACCENT = new THREE.Vector3(0.353, 0.663, 0.855);   // #5AA9DA, як у Linum

    renderer.setPixelRatio(DPR);
    renderer.setClearColor(0x000000, 1);

    // ---------- Місця частинок з маски іконки ----------

    function iconTargets() {
        const mask = window.LINUM_MASK;
        const size = mask.size;
        const raw = atob(mask.bits);
        const white = [];
        let minX = size, maxX = 0, minY = size, maxY = 0;
        for (let i = 0; i < size * size; i++) {
            if (raw.charCodeAt(i >> 3) & (1 << (i & 7))) {
                white.push(i);
                const x = i % size, y = Math.floor(i / size);
                minX = Math.min(minX, x); maxX = Math.max(maxX, x);
                minY = Math.min(minY, y); maxY = Math.max(maxY, y);
            }
        }
        const centerX = (minX + maxX + 1) / 2;
        const centerY = (minY + maxY + 1) / 2;
        const half = Math.max(maxX - minX, maxY - minY) / 2;

        const targets = new Float32Array(COUNT * 4);
        for (let i = 0; i < COUNT; i++) {
            const k = i * 4;
            if (Math.random() < 0.1) {
                // Частинка-пилинка: літає навколо, ледь тягнеться до свого місця
                const r = 1.25 * Math.cbrt(Math.random());
                const theta = Math.random() * Math.PI * 2;
                const phi = Math.acos(2 * Math.random() - 1);
                targets[k] = r * Math.sin(phi) * Math.cos(theta);
                targets[k + 1] = r * Math.sin(phi) * Math.sin(theta);
                targets[k + 2] = r * Math.cos(phi) * 0.6;
                targets[k + 3] = 0;
            } else {
                const index = white[Math.floor(Math.random() * white.length)];
                const px = (index % size) + Math.random() * 1.6 - 0.3;
                const py = Math.floor(index / size) + Math.random() * 1.6 - 0.3;
                targets[k] = (px - centerX) / half;
                targets[k + 1] = -(py - centerY) / half;
                targets[k + 2] = (Math.random() - 0.5) * 0.09;
                targets[k + 3] = 1;
            }
        }
        return targets;
    }

    function randomStart() {
        // На старті частинки розсипані, і за кілька секунд складаються в іконку
        const data = new Float32Array(COUNT * 4);
        for (let i = 0; i < COUNT; i++) {
            const r = 2.6 * Math.cbrt(Math.random());
            const theta = Math.random() * Math.PI * 2;
            const phi = Math.acos(2 * Math.random() - 1);
            data[i * 4] = r * Math.sin(phi) * Math.cos(theta);
            data[i * 4 + 1] = r * Math.sin(phi) * Math.sin(theta);
            data[i * 4 + 2] = r * Math.cos(phi);
            data[i * 4 + 3] = 1;
        }
        return data;
    }

    const randoms = new Float32Array(COUNT * 4);
    for (let i = 0; i < randoms.length; i++) randoms[i] = Math.random();

    function dataTexture(data) {
        const texture = new THREE.DataTexture(data, TEX, TEX, THREE.RGBAFormat, THREE.FloatType);
        texture.minFilter = THREE.NearestFilter;
        texture.magFilter = THREE.NearestFilter;
        texture.needsUpdate = true;
        return texture;
    }

    const targetTexture = dataTexture(iconTargets());
    const randomTexture = dataTexture(randoms);
    const startTexture = dataTexture(randomStart());

    // ---------- Допоміжне: малювання на весь екран у текстуру ----------

    const quadScene = new THREE.Scene();
    const quadCamera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
    const quad = new THREE.Mesh(new THREE.PlaneGeometry(2, 2));
    quad.frustumCulled = false;
    quadScene.add(quad);

    const QUAD_VERTEX = `
        varying vec2 vUv;
        void main() {
            vUv = uv;
            gl_Position = vec4(position.xy, 0.0, 1.0);
        }
    `;

    function shader(fragmentShader, uniforms) {
        return new THREE.ShaderMaterial({
            uniforms: uniforms,
            vertexShader: QUAD_VERTEX,
            fragmentShader: fragmentShader,
            depthTest: false,
            depthWrite: false,
        });
    }

    function pass(material, target) {
        quad.material = material;
        renderer.setRenderTarget(target);
        renderer.render(quadScene, quadCamera);
    }

    function renderTarget(width, height, type, filter) {
        return new THREE.WebGLRenderTarget(width, height, {
            type: type,
            format: THREE.RGBAFormat,
            minFilter: filter,
            magFilter: filter,
            wrapS: THREE.ClampToEdgeWrapping,
            wrapT: THREE.ClampToEdgeWrapping,
            depthBuffer: false,
            stencilBuffer: false,
        });
    }

    function doubleTarget(width, height, type, filter) {
        // Дві текстури: з однієї читаємо, в іншу пишемо, потім міняємо місцями
        let read = renderTarget(width, height, type, filter);
        let write = renderTarget(width, height, type, filter);
        return {
            get read() { return read; },
            get write() { return write; },
            swap() { const t = read; read = write; write = t; },
        };
    }

    const copyShader = shader(`
        uniform sampler2D uTexture;
        varying vec2 vUv;
        void main() { gl_FragColor = texture2D(uTexture, vUv); }
    `, { uTexture: { value: null } });

    // ---------- Рідина під курсором ----------

    const HALF = THREE.HalfFloatType;
    const LINEAR = THREE.LinearFilter;
    const velocity = doubleTarget(SIM, SIM, HALF, LINEAR);
    const dye = doubleTarget(DYE, DYE, HALF, LINEAR);
    const pressure = doubleTarget(SIM, SIM, HALF, THREE.NearestFilter);
    const divergence = renderTarget(SIM, SIM, HALF, THREE.NearestFilter);
    const curlTarget = renderTarget(SIM, SIM, HALF, THREE.NearestFilter);
    const simTexel = new THREE.Vector2(1 / SIM, 1 / SIM);
    const FLUID_DT = 1 / 60;

    const NEIGHBOURS = `
        uniform vec2 texel;
        varying vec2 vUv;
        vec2 uvL() { return vUv - vec2(texel.x, 0.0); }
        vec2 uvR() { return vUv + vec2(texel.x, 0.0); }
        vec2 uvT() { return vUv + vec2(0.0, texel.y); }
        vec2 uvB() { return vUv - vec2(0.0, texel.y); }
    `;

    const splatShader = shader(`
        uniform sampler2D uTarget;
        uniform float aspect;
        uniform vec3 color;
        uniform vec2 pointA;
        uniform vec2 pointB;
        uniform float radius;
        varying vec2 vUv;
        float segment(vec2 p, vec2 a, vec2 b) {
            vec2 pa = p - a, ba = b - a;
            float h = clamp(dot(pa, ba) / max(dot(ba, ba), 1e-8), 0.0, 1.0);
            return length(pa - ba * h);
        }
        void main() {
            vec2 p = vUv, a = pointA, b = pointB;
            p.x *= aspect; a.x *= aspect; b.x *= aspect;
            float d = segment(p, a, b);
            vec3 splat = exp(-d * d / radius) * color;
            gl_FragColor = vec4(texture2D(uTarget, vUv).xyz + splat, 1.0);
        }
    `, {
        uTarget: { value: null }, aspect: { value: 1 }, color: { value: new THREE.Vector3() },
        pointA: { value: new THREE.Vector2() }, pointB: { value: new THREE.Vector2() }, radius: { value: 0.001 },
    });

    const curlShader = shader(NEIGHBOURS + `
        uniform sampler2D uVelocity;
        void main() {
            float L = texture2D(uVelocity, uvL()).y;
            float R = texture2D(uVelocity, uvR()).y;
            float T = texture2D(uVelocity, uvT()).x;
            float B = texture2D(uVelocity, uvB()).x;
            gl_FragColor = vec4(0.5 * (R - L - T + B), 0.0, 0.0, 1.0);
        }
    `, { uVelocity: { value: null }, texel: { value: simTexel } });

    const vorticityShader = shader(NEIGHBOURS + `
        uniform sampler2D uVelocity;
        uniform sampler2D uCurl;
        uniform float curl;
        uniform float dt;
        void main() {
            float L = texture2D(uCurl, uvL()).x;
            float R = texture2D(uCurl, uvR()).x;
            float T = texture2D(uCurl, uvT()).x;
            float B = texture2D(uCurl, uvB()).x;
            float C = texture2D(uCurl, vUv).x;
            vec2 force = 0.5 * vec2(abs(T) - abs(B), abs(R) - abs(L));
            force /= length(force) + 0.0001;
            force *= curl * C;
            force.y *= -1.0;
            vec2 vel = texture2D(uVelocity, vUv).xy + force * dt;
            gl_FragColor = vec4(clamp(vel, -1000.0, 1000.0), 0.0, 1.0);
        }
    `, { uVelocity: { value: null }, uCurl: { value: null }, curl: { value: 30 }, dt: { value: FLUID_DT }, texel: { value: simTexel } });

    const divergenceShader = shader(NEIGHBOURS + `
        uniform sampler2D uVelocity;
        void main() {
            float L = texture2D(uVelocity, uvL()).x;
            float R = texture2D(uVelocity, uvR()).x;
            float T = texture2D(uVelocity, uvT()).y;
            float B = texture2D(uVelocity, uvB()).y;
            vec2 C = texture2D(uVelocity, vUv).xy;
            if (vUv.x - texel.x < 0.0) L = -C.x;
            if (vUv.x + texel.x > 1.0) R = -C.x;
            if (vUv.y + texel.y > 1.0) T = -C.y;
            if (vUv.y - texel.y < 0.0) B = -C.y;
            gl_FragColor = vec4(0.5 * (R - L + T - B), 0.0, 0.0, 1.0);
        }
    `, { uVelocity: { value: null }, texel: { value: simTexel } });

    const fadeShader = shader(`
        uniform sampler2D uTexture;
        uniform float value;
        varying vec2 vUv;
        void main() { gl_FragColor = value * texture2D(uTexture, vUv); }
    `, { uTexture: { value: null }, value: { value: 0.95 } });

    const pressureShader = shader(NEIGHBOURS + `
        uniform sampler2D uPressure;
        uniform sampler2D uDivergence;
        void main() {
            float L = texture2D(uPressure, uvL()).x;
            float R = texture2D(uPressure, uvR()).x;
            float T = texture2D(uPressure, uvT()).x;
            float B = texture2D(uPressure, uvB()).x;
            float div = texture2D(uDivergence, vUv).x;
            gl_FragColor = vec4((L + R + B + T - div) * 0.25, 0.0, 0.0, 1.0);
        }
    `, { uPressure: { value: null }, uDivergence: { value: null }, texel: { value: simTexel } });

    const gradientShader = shader(NEIGHBOURS + `
        uniform sampler2D uPressure;
        uniform sampler2D uVelocity;
        void main() {
            float L = texture2D(uPressure, uvL()).x;
            float R = texture2D(uPressure, uvR()).x;
            float T = texture2D(uPressure, uvT()).x;
            float B = texture2D(uPressure, uvB()).x;
            vec2 vel = texture2D(uVelocity, vUv).xy - vec2(R - L, T - B);
            gl_FragColor = vec4(vel, 0.0, 1.0);
        }
    `, { uPressure: { value: null }, uVelocity: { value: null }, texel: { value: simTexel } });

    const advectShader = shader(`
        uniform sampler2D uVelocity;
        uniform sampler2D uSource;
        uniform vec2 texel;
        uniform float dt;
        uniform float dissipation;
        varying vec2 vUv;
        void main() {
            vec2 coord = vUv - dt * texture2D(uVelocity, vUv).xy * texel;
            gl_FragColor = vec4(dissipation * texture2D(uSource, coord).xyz, 1.0);
        }
    `, { uVelocity: { value: null }, uSource: { value: null }, texel: { value: simTexel }, dt: { value: FLUID_DT }, dissipation: { value: 1 } });

    function splat(target, a, b, color, radius) {
        const u = splatShader.uniforms;
        u.uTarget.value = target.read.texture;
        u.aspect.value = window.innerWidth / window.innerHeight;
        u.pointA.value.copy(a);
        u.pointB.value.copy(b);
        u.color.value.set(color[0], color[1], color[2]);
        u.radius.value = radius;
        pass(splatShader, target.write);
        target.swap();
    }

    function stepFluid() {
        curlShader.uniforms.uVelocity.value = velocity.read.texture;
        pass(curlShader, curlTarget);

        vorticityShader.uniforms.uVelocity.value = velocity.read.texture;
        vorticityShader.uniforms.uCurl.value = curlTarget.texture;
        pass(vorticityShader, velocity.write);
        velocity.swap();

        divergenceShader.uniforms.uVelocity.value = velocity.read.texture;
        pass(divergenceShader, divergence);

        fadeShader.uniforms.uTexture.value = pressure.read.texture;
        fadeShader.uniforms.value.value = 0.95;
        pass(fadeShader, pressure.write);
        pressure.swap();

        pressureShader.uniforms.uDivergence.value = divergence.texture;
        for (let i = 0; i < 5; i++) {
            pressureShader.uniforms.uPressure.value = pressure.read.texture;
            pass(pressureShader, pressure.write);
            pressure.swap();
        }

        gradientShader.uniforms.uPressure.value = pressure.read.texture;
        gradientShader.uniforms.uVelocity.value = velocity.read.texture;
        pass(gradientShader, velocity.write);
        velocity.swap();

        advectShader.uniforms.uVelocity.value = velocity.read.texture;
        advectShader.uniforms.uSource.value = velocity.read.texture;
        advectShader.uniforms.dissipation.value = 0.98;
        pass(advectShader, velocity.write);
        velocity.swap();

        advectShader.uniforms.uVelocity.value = velocity.read.texture;
        advectShader.uniforms.uSource.value = dye.read.texture;
        advectShader.uniforms.dissipation.value = 0.97;
        pass(advectShader, dye.write);
        dye.swap();
    }

    // ---------- Симуляція частинок ----------

    const positions = doubleTarget(TEX, TEX, THREE.FloatType, THREE.NearestFilter);
    copyShader.uniforms.uTexture.value = startTexture;
    pass(copyShader, positions.read);

    const simulateShader = shader(`
        uniform sampler2D uPos;
        uniform sampler2D uTarget;
        uniform sampler2D uRand;
        uniform sampler2D uVelocity;
        uniform sampler2D uDye;
        uniform float uTime;
        uniform float uHz;
        uniform mat4 uMVP;
        uniform vec2 uFlowScale;
        varying vec2 vUv;

        // Вихрове поле: ротор від суми синусів, частинки в ньому плавно кружляють
        vec3 potential(vec3 p) {
            return vec3(
                sin(p.y * 1.7 + uTime * 0.30) + 0.5 * sin(p.z * 2.3 - uTime * 0.20),
                sin(p.z * 1.9 + uTime * 0.25) + 0.5 * sin(p.x * 2.7 + uTime * 0.15),
                sin(p.x * 1.3 - uTime * 0.35) + 0.5 * sin(p.y * 2.1 - uTime * 0.10)
            );
        }
        vec3 curlNoise(vec3 p) {
            const float e = 0.01;
            vec3 dx = vec3(e, 0.0, 0.0), dy = vec3(0.0, e, 0.0), dz = vec3(0.0, 0.0, e);
            vec3 x0 = potential(p - dx), x1 = potential(p + dx);
            vec3 y0 = potential(p - dy), y1 = potential(p + dy);
            vec3 z0 = potential(p - dz), z1 = potential(p + dz);
            return vec3(
                (y1.z - y0.z) - (z1.y - z0.y),
                (z1.x - z0.x) - (x1.z - x0.z),
                (x1.y - x0.y) - (y1.x - y0.x)
            ) / (2.0 * e);
        }

        void main() {
            vec3 pos = texture2D(uPos, vUv).xyz;
            vec4 target = texture2D(uTarget, vUv);
            vec4 rnd = texture2D(uRand, vUv);
            float onIcon = target.w;

            // Іконка ледь "дихає" вглиб
            vec3 home = target.xyz;
            home.z += sin(uTime * 0.6 + home.y * 2.5 + home.x) * 0.04 * onIcon;

            pos += curlNoise(pos * 1.2) * mix(0.0011, 0.00025, onIcon) * uHz;
            pos += (home - pos) * mix(0.004, mix(0.025, 0.06, rnd.x), onIcon) * uHz;

            // Поштовх рідини: де курсор пройшов, течія зносить частинки
            vec4 clip = uMVP * vec4(pos, 1.0);
            vec2 screen = clip.xy / clip.w * 0.5 + 0.5;
            if (clip.w > 0.0 && screen.x > 0.0 && screen.x < 1.0 && screen.y > 0.0 && screen.y < 1.0) {
                vec2 flow = texture2D(uVelocity, screen).xy;
                float density = min(texture2D(uDye, screen).r, 1.0);
                pos.xy += flow * uFlowScale * density * uHz;
                pos.z += (rnd.y - 0.5) * length(flow * uFlowScale) * 2.0 * density * uHz;
            }
            gl_FragColor = vec4(pos, 1.0);
        }
    `, {
        uPos: { value: null }, uTarget: { value: targetTexture }, uRand: { value: randomTexture },
        uVelocity: { value: null }, uDye: { value: null }, uTime: { value: 0 }, uHz: { value: 1 },
        uMVP: { value: new THREE.Matrix4() }, uFlowScale: { value: new THREE.Vector2() },
    });

    // ---------- Сцена з частинками ----------

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(30, 1, 0.1, 100);
    const CAMERA_BASE = new THREE.Vector3(0, 0, 6);
    camera.position.copy(CAMERA_BASE);
    const group = new THREE.Group();
    scene.add(group);

    const geometry = new THREE.BufferGeometry();
    const refs = new Float32Array(COUNT * 2);
    for (let i = 0; i < COUNT; i++) {
        refs[i * 2] = ((i % TEX) + 0.5) / TEX;
        refs[i * 2 + 1] = (Math.floor(i / TEX) + 0.5) / TEX;
    }
    geometry.setAttribute("position", new THREE.BufferAttribute(new Float32Array(COUNT * 3), 3));
    geometry.setAttribute("ref", new THREE.BufferAttribute(refs, 2));
    geometry.setAttribute("rand", new THREE.BufferAttribute(randoms, 4));

    const pointsMaterial = new THREE.ShaderMaterial({
        uniforms: {
            uPos: { value: null },
            uTime: { value: 0 },
            uSize: { value: (MOBILE ? 34 : 26) * DPR },
            uAccent: { value: ACCENT },
        },
        vertexShader: `
            attribute vec2 ref;
            attribute vec4 rand;
            uniform sampler2D uPos;
            uniform float uSize;
            varying vec4 vRand;
            void main() {
                vec3 pos = texture2D(uPos, ref).xyz;
                pos *= mix(1.0, 1.35, pow(rand.y, 150.0));
                vec4 view = modelViewMatrix * vec4(pos, 1.0);
                gl_PointSize = uSize * mix(0.5, 1.0, rand.z) / -view.z;
                gl_Position = projectionMatrix * view;
                vRand = rand;
            }
        `,
        fragmentShader: `
            uniform float uTime;
            uniform vec3 uAccent;
            varying vec4 vRand;
            void main() {
                vec2 p = gl_PointCoord * 2.0 - 1.0;
                float r = dot(p, p);
                if (r > 1.0) discard;
                // Кожна частинка: маленька кулька з м'яким світлом, що повільно повертається
                float angle = sin(uTime + vRand.z * 20.0) * 0.5 + 1.0;
                vec2 q = mat2(cos(angle), -sin(angle), sin(angle), cos(angle)) * p;
                vec3 normal = vec3(q.x, -q.y, sqrt(1.0 - r));
                float diffuse = max(dot(normal, normalize(vec3(-0.5, 0.6, 0.7))), 0.0);
                float shine = pow(max(dot(normal, normalize(vec3(-0.3, 0.4, 1.0))), 0.0), 24.0);
                float shade = 0.25 + 0.75 * diffuse + 0.6 * shine;
                vec3 color = vec3(mix(0.02, 0.14, vRand.x));
                color = mix(color, uAccent, pow(vRand.z, 60.0));
                float sparkle = 0.5 + (0.4 + sin(uTime * 4.0 + vRand.y * 20.0)) * pow(vRand.z, 10.0) * 2.5;
                gl_FragColor = vec4(color * shade * sparkle, 1.0);
            }
        `,
        transparent: true,
        blending: THREE.AdditiveBlending,
        depthTest: false,
        depthWrite: false,
    });

    const points = new THREE.Points(geometry, pointsMaterial);
    points.frustumCulled = false;
    group.add(points);

    // ---------- Розмір вікна: де стоїть іконка і якого вона розміру ----------

    let width = 1, height = 1, visibleWidth = 1, visibleHeight = 1;

    function freeArea() {
        // Частина екрана, не закрита текстом: іконка стає посередині неї
        if (width <= 760) return { left: 0, right: width, centerY: height * 0.36, share: 0.62 };
        const right = width - (width <= 1100 ? 24 + 320 + 24 : 90 + 380 + 24);
        const left = width <= 1000 ? 0 : 24 + 320 + 24;
        return { left: left, right: right, centerY: height / 2, share: 0.74 };
    }

    function resize() {
        width = window.innerWidth;
        height = window.innerHeight;
        renderer.setSize(width, height, false);
        camera.aspect = width / height;
        visibleHeight = 2 * CAMERA_BASE.z * Math.tan(THREE.MathUtils.degToRad(camera.fov / 2));
        visibleWidth = visibleHeight * camera.aspect;

        const area = freeArea();
        const centerX = (area.left + area.right) / 2;
        // Зсуваємо кадр так, щоб центр сцени припав на середину вільного місця
        camera.setViewOffset(width, height, width / 2 - centerX, height / 2 - area.centerY, width, height);

        const byHeight = area.share * visibleHeight / 2;
        const byWidth = 0.9 * (area.right - area.left) / width * visibleWidth / 2;
        group.scale.setScalar(Math.min(byHeight, byWidth));
    }
    window.addEventListener("resize", resize);
    resize();

    // ---------- Курсор ----------

    const pointer = { x: width / 2, y: height / 2, seen: false };
    const previous = new THREE.Vector2();
    const current = new THREE.Vector2();
    const lastPixel = { x: 0, y: 0 };
    let lastSplat = 0;

    function setPointer(x, y) {
        pointer.x = x;
        pointer.y = y;
        if (!pointer.seen) {
            pointer.seen = true;
            lastPixel.x = x;
            lastPixel.y = y;
        }
    }
    window.addEventListener("pointermove", function (event) { setPointer(event.clientX, event.clientY); });
    window.addEventListener("touchstart", function (event) {
        const touch = event.touches[0];
        setPointer(touch.clientX, touch.clientY);
        lastPixel.x = touch.clientX;
        lastPixel.y = touch.clientY;
    }, { passive: true });
    window.addEventListener("touchmove", function (event) {
        const touch = event.touches[0];
        setPointer(touch.clientX, touch.clientY);
    }, { passive: true });

    function mapClamp(value, inMin, inMax, outMin, outMax) {
        const t = Math.min(Math.max((value - inMin) / (inMax - inMin), 0), 1);
        return outMin + (outMax - outMin) * t;
    }

    function feedPointer(now) {
        if (!pointer.seen) return;
        const dx = pointer.x - lastPixel.x;
        const dy = pointer.y - lastPixel.y;
        const moved = Math.hypot(dx, dy);
        if (moved > 0.01) {
            const radius = mapClamp(moved, 0, 5, 0, 1) * 0.0022 * (MOBILE ? 0.8 : 1) + 0.0002;
            const force = mapClamp(moved, 0, 15, 0, 10);
            current.set(pointer.x / width, 1 - pointer.y / height);
            if (now - lastSplat > 50) previous.copy(current);
            else previous.set(lastPixel.x / width, 1 - lastPixel.y / height);
            splat(velocity, previous, current, [dx * force, -dy * force, 1], radius);
            splat(dye, previous, current, [1, 1, 1], radius);
            lastSplat = now;
        }
        lastPixel.x = pointer.x;
        lastPixel.y = pointer.y;
    }

    // ---------- Кадр ----------

    const lookTarget = new THREE.Vector3();
    const gaze = new THREE.Vector3();
    const mvp = new THREE.Matrix4();
    let lastTime = performance.now();
    const startTime = lastTime;

    function frame(now, still) {
        const delta = still ? 1 / 60 : Math.min((now - lastTime) / 1000, 1 / 20);
        lastTime = now;
        const time = (now - startTime) / 1000;
        const hz = delta * 60;

        // Камера трохи "дивиться" за курсором
        const mx = pointer.seen ? (pointer.x / width) * 2 - 1 : 0;
        const my = pointer.seen ? (pointer.y / height) * 2 - 1 : 0;
        gaze.set(CAMERA_BASE.x - mx * 0.6, CAMERA_BASE.y + my * 0.45, CAMERA_BASE.z);
        camera.position.lerp(gaze, 0.05);
        camera.lookAt(lookTarget);
        camera.updateMatrixWorld();
        group.rotation.y = Math.sin(time * 0.2) * 0.12;
        group.updateMatrixWorld();

        feedPointer(now);
        stepFluid();

        const scale = group.scale.x;
        const u = simulateShader.uniforms;
        u.uPos.value = positions.read.texture;
        u.uVelocity.value = velocity.read.texture;
        u.uDye.value = dye.read.texture;
        u.uTime.value = time;
        u.uHz.value = hz;
        mvp.multiplyMatrices(camera.projectionMatrix, camera.matrixWorldInverse).multiply(group.matrixWorld);
        u.uMVP.value.copy(mvp);
        // Швидкість рідини (клітинок за секунду) у зсув частинки за кадр
        u.uFlowScale.value.set(visibleWidth, visibleHeight).multiplyScalar(0.7 * FLUID_DT / SIM / scale);
        pass(simulateShader, positions.write);
        positions.swap();

        pointsMaterial.uniforms.uPos.value = positions.read.texture;
        pointsMaterial.uniforms.uTime.value = time;
        renderer.setRenderTarget(null);
        renderer.render(scene, camera);

        if (!still) requestAnimationFrame(frame);
    }

    // Для перевірки: index.html?warm=300 одразу прораховує 300 кадрів (5 секунд руху)
    const warm = Number(new URLSearchParams(window.location.search).get("warm")) || 0;
    for (let i = 0; i < Math.min(warm, 2000); i++) frame(startTime + i * 1000 / 60, true);
    lastTime = performance.now();
    requestAnimationFrame(frame);
})();
