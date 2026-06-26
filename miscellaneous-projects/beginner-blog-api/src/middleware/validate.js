// Builds a middleware that validates req.body against a Zod schema. On
// failure, sends 400 with the first issue. On success, replaces req.body
// with the parsed (and trimmed/coerced) data.

module.exports = function validate(schema) {
  return (req, res, next) => {
    const result = schema.safeParse(req.body);
    if (!result.success) {
      const issue = result.error.issues[0];
      const field = issue.path.join('.') || 'body';
      return next({ status: 400, message: `${field}: ${issue.message}` });
    }
    req.body = result.data;
    next();
  };
};
