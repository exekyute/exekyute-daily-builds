// Comments are always scoped to a post for reads and writes. Deletes use a
// flat /comments/:id path because clients usually have the comment ID alone.

const { z } = require('zod');
const prisma = require('../config/prisma');
const asyncHandler = require('../utils/asyncHandler');

const createSchema = z.object({
  content: z.string().min(1).max(1000),
});

const authorSelect = { id: true, username: true };

const listForPost = asyncHandler(async (req, res, next) => {
  const post = await prisma.post.findUnique({
    where: { id: req.params.postId },
  });
  if (!post) return next({ status: 404, message: 'Post not found' });

  const comments = await prisma.comment.findMany({
    where: { postId: req.params.postId },
    orderBy: { createdAt: 'asc' },
    include: { author: { select: authorSelect } },
  });
  res.json({ comments });
});

const create = asyncHandler(async (req, res, next) => {
  const post = await prisma.post.findUnique({
    where: { id: req.params.postId },
  });
  if (!post) return next({ status: 404, message: 'Post not found' });

  const comment = await prisma.comment.create({
    data: {
      content: req.body.content,
      postId: req.params.postId,
      authorId: req.user.id,
    },
    include: { author: { select: authorSelect } },
  });
  res.status(201).json({ comment });
});

const remove = asyncHandler(async (req, res, next) => {
  const existing = await prisma.comment.findUnique({
    where: { id: req.params.id },
  });
  if (!existing) return next({ status: 404, message: 'Comment not found' });
  if (existing.authorId !== req.user.id) {
    return next({
      status: 403,
      message: 'You can only delete your own comments',
    });
  }

  await prisma.comment.delete({ where: { id: req.params.id } });
  res.status(204).end();
});

module.exports = { listForPost, create, remove, createSchema };
