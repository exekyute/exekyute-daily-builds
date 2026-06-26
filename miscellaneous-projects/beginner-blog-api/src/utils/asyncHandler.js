// Wraps an async route handler so any thrown or rejected error is forwarded
// to Express's error pipeline. Without this, a rejected promise becomes an
// unhandled rejection and the client request hangs.

module.exports = (fn) => (req, res, next) => {
  Promise.resolve(fn(req, res, next)).catch(next);
};
