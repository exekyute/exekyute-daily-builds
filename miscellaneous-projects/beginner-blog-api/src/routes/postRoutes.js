const express = require('express');
const requireAuth = require('../middleware/auth');
const validate = require('../middleware/validate');
const {
  list,
  getOne,
  create,
  update,
  remove,
  createSchema,
  updateSchema,
} = require('../controllers/postController');

const router = express.Router();

router.get('/', list);
router.get('/:id', getOne);
router.post('/', requireAuth, validate(createSchema), create);
router.put('/:id', requireAuth, validate(updateSchema), update);
router.delete('/:id', requireAuth, remove);

module.exports = router;
