(function bootstrap(root, factory) {
  const auth = factory();
  if (typeof module === 'object' && module.exports) module.exports = auth;
  if (root) root.V5AdminAuth = auth;
})(typeof window === 'undefined' ? null : window, () => {
  'use strict';

  const TRANSIENT_KEY = 'gravitation.v5.admin.pkce';
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
      return JSON.parse(atob(padded));
    } catch { return {}; }
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
    if (!config || config.environment !== 'TEST' || !config.client_id || !config.redirect_uri) {
      throw new Error('oidc_configuration_required');
    }
    if (!config.issuer && !config.openid_configuration_url && !config.authorization_endpoint) {
      throw new Error('oidc_configuration_required');
    }
    return {...config, scopes: config.scopes || ['openid', 'email', 'profile']};
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
      if (!tokens.access_token) throw new Error('oidc_token_missing');
      const claims = decodeJwt(tokens.id_token || tokens.access_token);
      session = {accessToken: tokens.access_token, idToken: tokens.id_token || null, user: {name: claims.name || '', email: claims.email || ''}};
      return session;
    }
    return {signIn, consumeCallback, getSession: () => session, getAccessToken: () => session && session.accessToken, getIdToken: () => session && session.idToken, signOut: () => { session = null; storage.removeItem(TRANSIENT_KEY); }};
  }
  return {TRANSIENT_KEY, random, pkceChallenge, decodeJwt, tokenDiagnostics, normalizeConfig, resolveEndpoints, createAuthClient};
});
