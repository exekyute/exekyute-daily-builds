// Post CRUD. Public reads; authenticated writes; only the author can edit
// or delete their own post.

const { z } = require('zod');
const prisma = require('../config/prisma');
const asyncHandler = require('../utils/asyncHandler');

const createSchema = z.object({
  title: z.string().min(1).max(200),
  content: z.string().min(1),
});

// At least one field required so a PUT with an empty body is rejected.
const updateSchema = z
  .object({
    title: z.string().min(1).max(200).optional(),
    content: z.string().min(1).optional(),
  })
  .refine((data) => Object.keys(data).length > 0, {
    message: 'At least one field (title or content) must be provided',
  });

// `select` instead of `include` so we never accidentally return passwordHash.
const authorSelect = { id: true, username: true };

const list = asyncHandler(async (req, res) => {
  const page = Math.max(1, parseInt(req.query.page) || 1);
  const limit = Math.min(50, Math.max(1, parseInt(req.query.limit) || 10));
  const skip = (page - 1) * limit;

  const [posts, total] = await Promise.all([
    prisma.post.findMany({
      skip,
      take: limit,
      orderBy: { createdAt: 'desc' },
      include: { author: { select: authorSelect } },
    }),
    prisma.post.count(),
  ]);

  res.json({
    posts,
    page,
    limit,
    total,
    totalPages: Math.ceil(total / limit),
  });
});

const getOne = asyncHandler(async (req, res, next) => {
  const post = await prisma.post.findUnique({
    where: { id: req.params.id },
    include: {
      author: { select: authorSelect },
      comments: {
        orderBy: { createdAt: 'asc' },
        include: { author: { select: authorSelect } },
      },
    },
  });
  if (!post) return next({ status: 404, message: 'Post not found' });
  res.json({ post });
});

const create = asyncHandler(async (req, res) => {
  const post = await prisma.post.create({
    data: { ...req.body, authorId: req.user.id },
    include: { author: { select: authorSelect } },
  });
  res.status(201).json({ post });
});

const update = asyncHandler(async (req, res, next) => {
  const existing = await prisma.post.findUnique({
    where: { id: req.params.id },
  });
  if (!existing) return next({ status: 404, message: 'Post not found' });
  if (existing.authorId !== req.user.id) {
    return next({ status: 403, message: 'You can only edit your own posts' });
  }

  const post = await prisma.post.update({
    where: { id: req.params.id },
    data: req.body,
    include: { author: { select: authorSelect } },
  });
  res.json({ post });
});

const remove = asyncHandler(async (req, res, next) => {
  const existing = await prisma.post.findUnique({
    where: { id: req.params.id },
  });
  if (!existing) return next({ status: 404, message: 'Post not found' });
  if (existing.authorId !== req.user.id) {
    return next({ status: 403, message: 'You can only delete your own posts' });
  }

  await prisma.post.delete({ where: { id: req.params.id } });
  res.status(204).end();
});

module.exports = {
  list,
  getOne,
  create,
  update,
  remove,
  createSchema,
  updateSchema,
};
