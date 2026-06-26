// One Prisma client for the whole app. Importing this everywhere prevents
// opening a new database connection per request, which would exhaust the pool.

const { PrismaClient } = require('@prisma/client');

const prisma = new PrismaClient();

module.exports = prisma;
