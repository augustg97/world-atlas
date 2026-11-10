// Small WebGL2 helpers. Shaders live in web/shaders/*.glsl and are fetched, never embedded in
// JS strings (TRAPS C6: a backtick in a shader comment has blacked the canvas three times).

export async function loadShaderSource(url) {
  const src = await (await fetch(`${url}?v=${version.v}`)).text();
  const base = url.slice(0, url.lastIndexOf('/') + 1);
  const parts = await Promise.all(src.split('\n').map(async (line) => {
    const m = line.match(/^\s*#include\s+"([^"]+)"/);
    return m ? loadShaderSource(base + m[1]) : line;
  }));
  return parts.join('\n');
}

function compile(gl, type, src, name) {
  const s = gl.createShader(type);
  gl.shaderSource(s, src);
  gl.compileShader(s);
  if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) {
    const log = gl.getShaderInfoLog(s);
    throw new Error(`shader ${name} failed to compile:\n${log}`);
  }
  return s;
}

export async function program(gl, name) {
  const [vs, fs] = await Promise.all([loadShaderSource(`shaders/${name}.vert.glsl`), loadShaderSource(`shaders/${name}.frag.glsl`)]);
  const p = gl.createProgram();
  gl.attachShader(p, compile(gl, gl.VERTEX_SHADER, vs, name + '.vert'));
  gl.attachShader(p, compile(gl, gl.FRAGMENT_SHADER, fs, name + '.frag'));
  gl.linkProgram(p);
  if (!gl.getProgramParameter(p, gl.LINK_STATUS)) throw new Error(`program ${name} failed to link: ${gl.getProgramInfoLog(p)}`);
  const uniforms = {};
  const n = gl.getProgramParameter(p, gl.ACTIVE_UNIFORMS);
  for (let i = 0; i < n; i++) {
    const info = gl.getActiveUniform(p, i);
    uniforms[info.name.replace(/\[0\]$/, '')] = { loc: gl.getUniformLocation(p, info.name), type: info.type };
  }
  return { p, uniforms, name };
}

/** Set uniforms from a plain object. Unknown names are ignored (a uniform the compiler removed is not an error). */
export function setUniforms(gl, prog, values) {
  for (const k in values) {
    const u = prog.uniforms[k];
    if (!u) continue;
    const v = values[k];
    switch (u.type) {
      case gl.FLOAT: gl.uniform1f(u.loc, v); break;
      case gl.INT: case gl.BOOL: case gl.SAMPLER_2D: case gl.SAMPLER_2D_ARRAY: gl.uniform1i(u.loc, v); break;
      case gl.FLOAT_VEC2: gl.uniform2fv(u.loc, v); break;
      case gl.FLOAT_VEC3: gl.uniform3fv(u.loc, v); break;
      case gl.FLOAT_VEC4: gl.uniform4fv(u.loc, v); break;
      case gl.FLOAT_MAT3: gl.uniformMatrix3fv(u.loc, false, v); break;
      default: throw new Error(`uniform ${k}: unhandled type ${u.type}`);
    }
  }
}

/** The data version: appended to every field and data URL so a stale cache can never be shown. */
export const version = { v: '' };
export async function loadVersion() {
  try { version.v = (await (await fetch('version.json', { cache: 'no-store' })).json()).data; } catch (e) { version.v = String(Date.now()); }
  return version.v;
}
/** A same-origin data URL with the version stamp; remote URLs pass through untouched. */
export const stamped = (url) => (/^https?:/.test(url) ? url : `${url}${url.includes('?') ? '&' : '?'}v=${version.v}`);
export const getJSON = (url) => fetch(stamped(url)).then((r) => { if (!r.ok) throw new Error(`${url}: HTTP ${r.status}`); return r.json(); });

export async function loadBitmap(url) {
  const r = await fetch(stamped(url));
  if (!r.ok) throw new Error(`${url}: HTTP ${r.status}`);
  // no colour management and no alpha premultiplication: the bytes in the file are the data
  return createImageBitmap(await r.blob(), { colorSpaceConversion: 'none', premultiplyAlpha: 'none' });
}

/** A 2D texture from an image. opts: {format:'rgb'|'r'|'rg', mips, wrapS, filter, aniso} */
export function texFromImage(gl, img, opts = {}) {
  const t = gl.createTexture();
  gl.bindTexture(gl.TEXTURE_2D, t);
  gl.pixelStorei(gl.UNPACK_ALIGNMENT, 1);
  gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, false);
  gl.pixelStorei(gl.UNPACK_COLORSPACE_CONVERSION_WEBGL, gl.NONE);
  const f = { rgb: [gl.RGB8, gl.RGB], r: [gl.R8, gl.RED], rg: [gl.RG8, gl.RG], rgba: [gl.RGBA8, gl.RGBA] }[opts.format || 'rgb'];
  gl.texImage2D(gl.TEXTURE_2D, 0, f[0], f[1], gl.UNSIGNED_BYTE, img);
  finishTex(gl, opts);
  return t;
}

export function finishTex(gl, opts = {}) {
  const mips = opts.mips !== false;
  if (mips) gl.generateMipmap(gl.TEXTURE_2D);
  const nearest = opts.filter === 'nearest';
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, nearest ? gl.NEAREST : (mips ? gl.LINEAR_MIPMAP_LINEAR : gl.LINEAR));
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, nearest ? gl.NEAREST : gl.LINEAR);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.REPEAT);              // longitude is periodic
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
  const ext = gl.getExtension('EXT_texture_filter_anisotropic');
  if (ext && mips && !nearest) gl.texParameterf(gl.TEXTURE_2D, ext.TEXTURE_MAX_ANISOTROPY_EXT, Math.min(8, gl.getParameter(ext.MAX_TEXTURE_MAX_ANISOTROPY_EXT)));
}

export function texFromData(gl, w, h, data, opts = {}) {
  const t = gl.createTexture();
  gl.bindTexture(gl.TEXTURE_2D, t);
  gl.pixelStorei(gl.UNPACK_ALIGNMENT, 1);
  const f = { r: [gl.R8, gl.RED], rg: [gl.RG8, gl.RG], rgb: [gl.RGB8, gl.RGB], rgba: [gl.RGBA8, gl.RGBA] }[opts.format || 'rgba'];
  gl.texImage2D(gl.TEXTURE_2D, 0, f[0], w, h, 0, f[1], gl.UNSIGNED_BYTE, data);
  finishTex(gl, opts);
  return t;
}

/** A 1x1 placeholder so every sampler is always bound to something valid. */
export function texSolid(gl, rgba = [0, 0, 0, 255]) {
  return texFromData(gl, 1, 1, new Uint8Array(rgba), { format: 'rgba', mips: false });
}

/** Pack two single-channel images into one RG8 texture on the GPU (no CPU readback). */
export function packRG(gl, imgR, imgG, w, h) {
  const a = texFromImage(gl, imgR, { format: 'r', mips: false });
  const b = texFromImage(gl, imgG, { format: 'r', mips: false });
  const out = gl.createTexture();
  gl.bindTexture(gl.TEXTURE_2D, out);
  gl.texStorage2D(gl.TEXTURE_2D, Math.floor(Math.log2(Math.max(w, h))) + 1, gl.RG8, w, h);
  const fb = gl.createFramebuffer();
  gl.bindFramebuffer(gl.FRAMEBUFFER, fb);
  gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, out, 0);
  if (!packRG.prog) {
    const vs = compile(gl, gl.VERTEX_SHADER, '#version 300 es\nout vec2 v;void main(){vec2 p=vec2(float((gl_VertexID<<1)&2),float(gl_VertexID&2));v=p;gl_Position=vec4(p*2.0-1.0,0.0,1.0);}', 'pack.vert');
    const fs = compile(gl, gl.FRAGMENT_SHADER, '#version 300 es\nprecision highp float;uniform sampler2D a;uniform sampler2D b;in vec2 v;out vec4 o;void main(){o=vec4(texture(a,v).r,texture(b,v).r,0.0,1.0);}', 'pack.frag');
    const p = gl.createProgram(); gl.attachShader(p, vs); gl.attachShader(p, fs); gl.linkProgram(p);
    packRG.prog = p;
  }
  gl.useProgram(packRG.prog);
  gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_2D, a);
  gl.activeTexture(gl.TEXTURE1); gl.bindTexture(gl.TEXTURE_2D, b);
  gl.uniform1i(gl.getUniformLocation(packRG.prog, 'a'), 0);
  gl.uniform1i(gl.getUniformLocation(packRG.prog, 'b'), 1);
  gl.viewport(0, 0, w, h);
  gl.disable(gl.BLEND);
  gl.drawArrays(gl.TRIANGLES, 0, 3);
  gl.bindFramebuffer(gl.FRAMEBUFFER, null);
  gl.deleteFramebuffer(fb); gl.deleteTexture(a); gl.deleteTexture(b);
  gl.activeTexture(gl.TEXTURE0);
  gl.bindTexture(gl.TEXTURE_2D, out);
  finishTex(gl, {});
  return out;
}

/** Twelve stacked months (one image, w x 12h) -> a TEXTURE_2D_ARRAY of 12 layers. */
export function texArrayFromPixels(gl, w, h, layers, rgba) {
  const t = gl.createTexture();
  gl.bindTexture(gl.TEXTURE_2D_ARRAY, t);
  gl.pixelStorei(gl.UNPACK_ALIGNMENT, 1);
  gl.texImage3D(gl.TEXTURE_2D_ARRAY, 0, gl.RGBA8, w, h, layers, 0, gl.RGBA, gl.UNSIGNED_BYTE, rgba);
  gl.texParameteri(gl.TEXTURE_2D_ARRAY, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
  gl.texParameteri(gl.TEXTURE_2D_ARRAY, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
  gl.texParameteri(gl.TEXTURE_2D_ARRAY, gl.TEXTURE_WRAP_S, gl.REPEAT);
  gl.texParameteri(gl.TEXTURE_2D_ARRAY, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
  return t;
}

/** Read an image's exact pixel values on the CPU. */
export function pixelsOf(img, w = img.width, h = img.height) {
  const c = new OffscreenCanvas(w, h);
  const ctx = c.getContext('2d', { willReadFrequently: true, colorSpace: 'srgb' });
  ctx.imageSmoothingEnabled = w !== img.width;
  ctx.imageSmoothingQuality = 'high';
  ctx.drawImage(img, 0, 0, w, h);
  return ctx.getImageData(0, 0, w, h).data;
}
