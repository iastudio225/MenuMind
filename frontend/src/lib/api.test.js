import api, { SESSION_INVALIDATED_EVENT } from "./api";

function response(config, status = 200, data = {}) {
  return { config, data, headers: {}, status, statusText: "OK" };
}

function rejectStatus(config, status) {
  return Promise.reject({ config, response: { config, status, data: {} } });
}

function deferred() {
  let resolve;
  const promise = new Promise((done) => { resolve = done; });
  return { promise, resolve };
}

describe("API session refresh", () => {
  let invalidated;

  beforeEach(() => {
    invalidated = jest.fn();
    window.addEventListener(SESSION_INVALIDATED_EVENT, invalidated);
  });

  afterEach(() => {
    window.removeEventListener(SESSION_INVALIDATED_EVENT, invalidated);
    delete api.defaults.adapter;
  });

  test("replays a protected request once after a successful refresh", async () => {
    const calls = [];
    api.defaults.adapter = async (config) => {
      calls.push(config.url);
      if (config.url === "/auth/refresh") return response(config);
      if (!config._retry) return rejectStatus(config, 401);
      return response(config, 200, { ok: true });
    };

    await expect(api.get("/admin/metrics")).resolves.toMatchObject({ data: { ok: true } });
    expect(calls.filter((url) => url === "/auth/refresh")).toHaveLength(1);
    expect(calls.filter((url) => url === "/admin/metrics")).toHaveLength(2);
    expect(invalidated).not.toHaveBeenCalled();
  });

  test("invalidates the session on refresh 401 without retrying indefinitely", async () => {
    const calls = [];
    api.defaults.adapter = async (config) => {
      calls.push(config.url);
      if (config.url === "/auth/refresh") return rejectStatus(config, 401);
      return rejectStatus(config, 401);
    };

    await expect(api.get("/admin/metrics")).rejects.toMatchObject({ response: { status: 401 } });
    expect(calls).toEqual(["/admin/metrics", "/auth/refresh"]);
    expect(invalidated).toHaveBeenCalledTimes(1);
  });

  test("does not invalidate the session for a refresh network failure", async () => {
    api.defaults.adapter = async (config) => {
      if (config.url === "/auth/refresh") throw { config, request: {} };
      return rejectStatus(config, 401);
    };

    await expect(api.get("/admin/metrics")).rejects.toMatchObject({ response: { status: 401 } });
    expect(invalidated).not.toHaveBeenCalled();
  });

  test("shares one refresh across simultaneous protected 401 responses", async () => {
    const gate = deferred();
    const calls = [];
    api.defaults.adapter = async (config) => {
      calls.push(config.url);
      if (config.url === "/auth/refresh") {
        await gate.promise;
        return response(config);
      }
      if (!config._retry) return rejectStatus(config, 401);
      return response(config, 200, { ok: true });
    };

    const requests = [api.get("/admin/metrics"), api.get("/admin/restaurants")];
    await Promise.resolve();
    await Promise.resolve();
    gate.resolve();
    await expect(Promise.all(requests)).resolves.toHaveLength(2);
    expect(calls.filter((url) => url === "/auth/refresh")).toHaveLength(1);
    expect(invalidated).not.toHaveBeenCalled();
  });

  test("does not refresh authentication endpoints", async () => {
    api.defaults.adapter = async (config) => rejectStatus(config, 401);

    await expect(api.get("/auth/me")).rejects.toMatchObject({ response: { status: 401 } });
    expect(invalidated).not.toHaveBeenCalled();
  });
});
