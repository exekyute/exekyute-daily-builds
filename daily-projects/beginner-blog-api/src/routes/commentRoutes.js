// Comments live on two URL shapes:
//   - /api/posts/:postId/comments   (list + create, scoped to a post)
//   - /api/comments/:id             (delete, when you only have a comment ID)

const express = require('express');
const requireAuth = require('../middleware/auth');
const validate = require('../middleware/validate');
const {
  listForPost,
  create,
  remove,
  createSchema,
} = require('../controllers/commentController');

// mergeParams: true so this router can read :postId from the parent path.
const postScoped = express.Router({ mergeParams: true });
postScoped.get('/', listForPost);
postScoped.post('/', requireAuth, validate(createSchema), create);

const flat = express.Router();
flat.delete('/:id', requireAuth, remove);

module.exports = { postScoped, flat };
