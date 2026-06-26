// Reads `Authorization: Bearer <token>`, verifies the JWT, and attaches the
// decoded user to req.user. Any route guarded by this middleware can trust
// that req.user.id and req.user.username exist.

const jwt = require('jsonwebtoken');

module.exports = function requireAuth(req, res, next) {
  const header = req.headers.authorization || '';
  const [scheme, token] = header.split(' ');

  if (scheme !== 'Bearer' || !token) {
    return next({ status: 401, message: 'Missing or malformed Authorization header' });
  }

  try {
    const payload = jwt.verify(token, process.env.JWT_SECRET);
    req.user = { id: payload.sub, username: payload.username };
    next();
  } catch (err) {
    next({ status: 401, message: 'Invalid or expired token' });
  }
};
