// Final middleware in the chain. Catches anything passed to next(err) and
// returns a consistent JSON shape: { error: { message, status } }.

function errorHandler(err, req, res, next) {
  const status = err.status || 500;
  // For 500s, hide the real message from clients to avoid leaking internals.
  const message = status === 500 ? 'Internal server error' : err.message;

  if (status === 500) {
    console.error(err);
  }

  res.status(status).json({ error: { message, status } });
}

function notFound(req, res, next) {
  const err = new Error(`Route not found: ${req.method} ${req.originalUrl}`);
  err.status = 404;
  next(err);
}

module.exports = { errorHandler, notFound };
