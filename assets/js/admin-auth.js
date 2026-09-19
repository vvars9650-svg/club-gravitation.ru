(function bootstrap(root, factory) {
  const auth = factory();
  if (typeof module === 'object' && module.exports) module.exports = auth;
  if (root) root.V5AdminAuth = auth;
})(typeof window === 'undefined' ? null : window, () => {
  'use strict';

  const TRANSIENT_KEY = 'gravitation.v5.admin.pkce';
  const OIDC_SCOPES = Object.freeze(['openid', 'email', 'profile']);
  const TEST_ISSUER = 'https://auth.yandex.cloud';
  const TEST_DISCOVERY_URL = `${TEST_ISSUER}/.well-known/openid-configuration`;
  const TEST_CLIENT_ID = 'aje25t7tefbfr547phru';
  const base64url = (bytes) => {
    let binary = '';
    bytes.forEach((byte) => { binary += String.fromCharCode(byte); });
    return btoa(binary).replace(/\+/gu, '-').replace(/\//gu, '_').replace(/=+$/gu, '');
  };
  const random = (cryptoImpl, size = 32) => {
    const bytes = new Uint8Array(size);
    cryptoImpl.getRandomValues(bytes);
    return base64url(bytes);
  };
  const pkceChallenge = async (verifier, cryptoImpl) => {
    const bytes = new TextEncoder().encode(verifier);
    return base64url(new Uint8Array(await cryptoImpl.subtle.digest('SHA-256', bytes)));
  };
  const decodeJwt = (token) => {
    const part = String(token || '').split('.')[1];
    if (!part) return {};
    try {
      const normalized = part.replace(/-/gu, '+').replace(/_/gu, '/');
      const padded = normalized + '='.repeat((4 - normalized.length % 4) % 4);
      const bytes = Uint8Array.from(atob(padded), (char) => char.charCodeAt(0));
      return JSON.parse(new TextDecoder('utf-8', {fatal: true}).decode(bytes));
    } catch { return {}; }
  };
  const normalizeOidcDisplayNameClaim = (value) => {
    if (typeof value !== 'string' || !value) return value || '';
    if (!/[ÃÂÐÑ]/.test(value)) return value;
    try {
      const cp1252 = {'€':0x80, '‚':0x82, 'ƒ':0x83, '„':0x84, '…':0x85, '†':0x86, '‡':0x87, 'ˆ':0x88, '‰':0x89, 'Š':0x8a, '‹':0x8b, 'Œ':0x8c, 'Ž':0x8e, '‘':0x91, '’':0x92, '“':0x93, '”':0x94, '•':0x95, '–':0x96, '—':0x97, '˜':0x98, '™':0x99, 'š':0x9a, '›':0x9b, 'œ':0x9c, 'ž':0x9e, 'Ÿ':0x9f};
      const bytes = Uint8Array.from(value, (char) => cp1252[char] ?? char.charCodeAt(0) & 0xff);
      const repaired = new TextDecoder('utf-8', {fatal: true}).decode(bytes);
      return /[\u0400-\u04ff]/.test(repaired) ? repaired : value;
    } catch (_) {
      return value;
    }
  };

  const displayNameFromClaims = (claims) => {
    const claim = (key) => normalizeOidcDisplayNameClaim(typeof claims?.[key] === 'string' ? claims[key].trim() : '');
    const given = claim('given_name');
    const family = claim('family_name');
    return [given, family].filter(Boolean).join(' ') || claim('name') || claim('preferred_username');
  };
  const tokenDiagnostics = (token, includeScope = false) => {
    const segments = String(token || '').split('.');
    const claims = segments.length === 3 ? decodeJwt(token) : {};
    const isJwt = segments.length === 3 && Object.keys(claims).length > 0;
    const result = {
      is_jwt: isJwt,
      segment_count: token ? segments.length : 0,
      iss: isJwt ? claims.iss || null : null,
      aud: isJwt ? claims.aud || null : null,
      sub_present: isJwt && typeof claims.sub === 'string' && claims.sub.length > 0,
      exp: isJwt ? claims.exp || null : null,
      claim_names: isJwt ? Object.keys(claims).sort() : []
    };
    if (includeScope) result.scope = isJwt ? claims.scope || null : null;
    return result;
  };
  const normalizeConfig = (config) => {
    if (!config || !['TEST', 'PROD'].includes(config.environment) || config.client_id !== TEST_CLIENT_ID || !config.redirect_uri) {
      throw new Error('oidc_configuration_required');
    }
    if (config.issuer !== TEST_ISSUER || config.openid_configuration_url !== TEST_DISCOVERY_URL) {
      throw new Error('oidc_configuration_required');
    }
    let redirect;
    try { redirect = new URL(config.redirect_uri); } catch { throw new Error('oidc_configuration_required'); }
    const loopback = redirect.hostname === '127.0.0.1' || redirect.hostname === 'localhost';
    if ((!loopback && redirect.protocol !== 'https:') || (loopback && !['http:', 'https:'].includes(redirect.protocol))
      || redirect.username || redirect.password || redirect.search || redirect.hash || !redirect.pathname.endsWith('/')) {
      throw new Error('oidc_configuration_required');
    }
    const scopes = config.scopes;
    if (!Array.isArray(scopes) || scopes.length !== OIDC_SCOPES.length
      || !OIDC_SCOPES.every((scope, index) => scopes[index] === scope)) {
      throw new Error('oidc_configuration_required');
    }
    return {...config, scopes: [...OIDC_SCOPES]};
  };
  async function resolveEndpoints(config, fetchImpl) {
    const known = config.authorization_endpoint && config.token_endpoint;
    if (known) return config;
    const url = config.openid_configuration_url || `${String(config.issuer).replace(/\/$/u, '')}/.well-known/openid-configuration`;
    const response = await fetchImpl(url, {method: 'GET'});
    if (!response.ok) throw new Error('oidc_discovery_failed');
    const discovered = await response.json();
    if (!discovered.authorization_endpoint || !discovered.token_endpoint) throw new Error('oidc_discovery_failed');
    return {...config, authorization_endpoint: discovered.authorization_endpoint, token_endpoint: discovered.token_endpoint};
  }
  function createAuthClient({config, fetchImpl, cryptoImpl, storage, location}) {
    const initialConfig = normalizeConfig(config);
    const page = new URL(location && location.href || '');
    const redirect = new URL(initialConfig.redirect_uri);
    if (page.origin !== redirect.origin || page.pathname !== redirect.pathname
      || typeof fetchImpl !== 'function' || !cryptoImpl || typeof cryptoImpl.getRandomValues !== 'function'
      || !cryptoImpl.subtle || typeof cryptoImpl.subtle.digest !== 'function' || !storage) {
      throw new Error('oidc_configuration_required');
    }
    let session = null;
    async function signIn() {
      const resolved = await resolveEndpoints(initialConfig, fetchImpl);
      const verifier = random(cryptoImpl);
      const state = random(cryptoImpl);
      storage.setItem(TRANSIENT_KEY, JSON.stringify({state, verifier}));
      const query = new URLSearchParams({response_type: 'code', client_id: resolved.client_id, redirect_uri: resolved.redirect_uri, scope: resolved.scopes.join(' '), state, code_challenge: await pkceChallenge(verifier, cryptoImpl), code_challenge_method: 'S256'});
      location.assign(`${resolved.authorization_endpoint}?${query}`);
    }
    async function consumeCallback(url = location.href) {
      const callback = new URL(url);
      const code = callback.searchParams.get('code');
      if (!code) return null;
      const transient = JSON.parse(storage.getItem(TRANSIENT_KEY) || 'null');
      const state = callback.searchParams.get('state');
      if (!transient || !state || transient.state !== state) throw new Error('oidc_state_mismatch');
      const resolved = await resolveEndpoints(initialConfig, fetchImpl);
      const body = new URLSearchParams({grant_type: 'authorization_code', code, redirect_uri: resolved.redirect_uri, client_id: resolved.client_id, code_verifier: transient.verifier});
      const response = await fetchImpl(resolved.token_endpoint, {method: 'POST', headers: {'Content-Type': 'application/x-www-form-urlencoded'}, body: body.toString()});
      storage.removeItem(TRANSIENT_KEY);
      if (!response.ok) throw new Error('oidc_token_exchange_failed');
      const tokens = await response.json();
      if (typeof tokens.id_token !== 'string' || !tokens.id_token.trim()) throw new Error('oidc_id_token_missing');
      const claims = decodeJwt(tokens.id_token);
      session = {gatewayToken: tokens.id_token, idToken: tokens.id_token, user: {name: displayNameFromClaims(claims), email: claims.email || ''}};
      return session;
    }
    return {signIn, consumeCallback, getSession: () => session, getGatewayToken: () => session && session.gatewayToken, getIdToken: () => session && session.idToken, signOut: () => { session = null; storage.removeItem(TRANSIENT_KEY); }};
  }
  return {TRANSIENT_KEY, OIDC_SCOPES, TEST_ISSUER, TEST_DISCOVERY_URL, TEST_CLIENT_ID, random, pkceChallenge, decodeJwt, normalizeOidcDisplayNameClaim, displayNameFromClaims, tokenDiagnostics, normalizeConfig, resolveEndpoints, createAuthClient};
});
