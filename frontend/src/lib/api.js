import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const api = axios.create({
  baseURL: API,
  withCredentials: true,
});

// StrictMode intentionally replays mount effects in development. Share only
// identical in-flight GETs so that replay does not double the database load.
const inFlightGets = new Map();
const stableKey = (value) => {
  if (Array.isArray(value)) return `[${value.map(stableKey).join(",")}]`;
  if (value && typeof value === "object") {
    return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${stableKey(value[key])}`).join(",")}}`;
  }
  return JSON.stringify(value);
};
const axiosGet = api.get.bind(api);
api.get = (url, config = {}) => {
  const key = `${config.baseURL || api.defaults.baseURL}|${url}|${stableKey(config.params || {})}`;
  const pending = inFlightGets.get(key);
  if (pending) return pending;
  const request = axiosGet(url, config).finally(() => inFlightGets.delete(key));
  inFlightGets.set(key, request);
  return request;
};

let refreshing = null;
export const SESSION_INVALIDATED_EVENT = "menumind:session-invalidated";

function refreshSession() {
  if (!refreshing) {
    refreshing = api.post("/auth/refresh")
      .then(() => true)
      .catch((error) => {
        if (error.response?.status === 401 && typeof window !== "undefined") {
          window.dispatchEvent(new Event(SESSION_INVALIDATED_EVENT));
        }
        return false;
      })
      .finally(() => {
        refreshing = null;
      });
  }
  return refreshing;
}

api.interceptors.response.use(
  (res) => res,
  async (error) => {
    const original = error.config;
    const status = error.response?.status;
    if (status === 401 && original && !original._retry && !original.url?.includes("/auth/")) {
      original._retry = true;
      const refreshed = await refreshSession();
      if (refreshed) {
        return api(original);
      }
    }
    return Promise.reject(error);
  }
);

export default api;
export { API };
