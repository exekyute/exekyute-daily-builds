// Seeds the database with fake users, posts, and comments. Safe to re-run:
// it wipes existing data first so the result is deterministic.
//
// Run with: npm run prisma:seed
// All seeded users share the password: password123

require('dotenv').config();
const bcrypt = require('bcrypt');
const { faker } = require('@faker-js/faker');
const prisma = require('../src/config/prisma');

const USERS = 5;
const POSTS = 20;
const COMMENTS = 50;

async function main() {
  console.log('Clearing existing data...');
  // onDelete: Cascade in the schema would handle this, but doing it explicitly
  // makes the seed faster to reason about.
  await prisma.comment.deleteMany();
  await prisma.post.deleteMany();
  await prisma.user.deleteMany();

  console.log(`Creating ${USERS} users...`);
  const passwordHash = await bcrypt.hash('password123', 10);
  const users = [];
  for (let i = 0; i < USERS; i++) {
    users.push(
      await prisma.user.create({
        data: {
          email: `user${i}_${faker.internet.email().toLowerCase()}`,
          username: `${faker.internet.userName().toLowerCase()}_${i}`,
          passwordHash,
        },
      })
    );
  }

  console.log(`Creating ${POSTS} posts...`);
  const posts = [];
  for (let i = 0; i < POSTS; i++) {
    posts.push(
      await prisma.post.create({
        data: {
          title: faker.lorem.sentence({ min: 4, max: 8 }),
          content: faker.lorem.paragraphs({ min: 2, max: 5 }, '\n\n'),
          authorId: faker.helpers.arrayElement(users).id,
        },
      })
    );
  }

  console.log(`Creating ${COMMENTS} comments...`);
  for (let i = 0; i < COMMENTS; i++) {
    await prisma.comment.create({
      data: {
        content: faker.lorem.sentences({ min: 1, max: 3 }),
        postId: faker.helpers.arrayElement(posts).id,
        authorId: faker.helpers.arrayElement(users).id,
      },
    });
  }

  console.log('Seed complete. Login with any seeded email / password123');
}

main()
  .catch((err) => {
    console.error(err);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
