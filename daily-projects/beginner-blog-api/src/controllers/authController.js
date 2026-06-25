// Register and login handlers. Both return { user, token } on success.

const bcrypt = require('bcrypt');
const jwt = require('jsonwebtoken');
const { z } = require('zod');
const prisma = require('../config/prisma');
const asyncHandler = require('../utils/asyncHandler');

// 10 rounds is the standard balance between security and login speed.
const BCRYPT_ROUNDS = 10;
// 7 days keeps things simple for a v1 API; no refresh tokens needed yet.
const JWT_EXPIRES_IN = '7d';

const registerSchema = z.object({
  email: z.string().email(),
  username: z.string().min(3).max(30),
  password: z.string().min(8).max(100),
});

const loginSchema = z.object({
  email: z.string().email(),
  password: z.string().min(1),
});

function signToken(user) {
  return jwt.sign(
    { sub: user.id, username: user.username },
    process.env.JWT_SECRET,
    { expiresIn: JWT_EXPIRES_IN }
  );
}

function publicUser(user) {
  // Strip passwordHash before returning user data to a client.
  return {
    id: user.id,
    email: user.email,
    username: user.username,
    createdAt: user.createdAt,
  };
}

const register = asyncHandler(async (req, res) => {
  const { email, username, password } = req.body;

  const existing = await prisma.user.findFirst({
    where: { OR: [{ email }, { username }] },
  });
  if (existing) {
    const field = existing.email === email ? 'email' : 'username';
    return res.status(409).json({
      error: { message: `${field} already in use`, status: 409 },
    });
  }

  const passwordHash = await bcrypt.hash(password, BCRYPT_ROUNDS);
  const user = await prisma.user.create({
    data: { email, username, passwordHash },
  });

  res.status(201).json({ user: publicUser(user), token: signToken(user) });
});

const login = asyncHandler(async (req, res) => {
  const { email, password } = req.body;

  const user = await prisma.user.findUnique({ where: { email } });
  // Same response whether the email or the password is wrong -- avoids
  // leaking which accounts exist.
  const valid = user && (await bcrypt.compare(password, user.passwordHash));
  if (!valid) {
    return res.status(401).json({
      error: { message: 'Invalid credentials', status: 401 },
    });
  }

  res.json({ user: publicUser(user), token: signToken(user) });
});

module.exports = { register, login, registerSchema, loginSchema };
