// Integration tests for /api/posts covering auth-gated CRUD.

const request = require('supertest');
const app = require('../src/app');
const prisma = require('../src/config/prisma');

const user = {
  email: 'posts-test@example.com',
  username: 'poststestuser',
  password: 'password123',
};
let token;
let userId;

beforeAll(async () => {
  await prisma.user.deleteMany({ where: { email: user.email } });
  const res = await request(app).post('/api/auth/register').send(user);
  token = res.body.token;
  userId = res.body.user.id;
});

afterAll(async () => {
  // Cascade delete removes the user's posts and comments too.
  await prisma.user.deleteMany({ where: { id: userId } });
  await prisma.$disconnect();
});

describe('Posts CRUD', () => {
  let postId;

  it('creates a post when authenticated', async () => {
    const res = await request(app)
      .post('/api/posts')
      .set('Authorization', `Bearer ${token}`)
      .send({ title: 'Hello', content: 'World' });
    expect(res.status).toBe(201);
    expect(res.body.post.title).toBe('Hello');
    postId = res.body.post.id;
  });

  it('rejects unauthenticated create', async () => {
    const res = await request(app)
      .post('/api/posts')
      .send({ title: 'Nope', content: 'Nope' });
    expect(res.status).toBe(401);
  });

  it('lists posts publicly with pagination', async () => {
    const res = await request(app).get('/api/posts?page=1&limit=10');
    expect(res.status).toBe(200);
    expect(Array.isArray(res.body.posts)).toBe(true);
    expect(res.body.page).toBe(1);
  });

  it('fetches a single post with author and comments', async () => {
    const res = await request(app).get(`/api/posts/${postId}`);
    expect(res.status).toBe(200);
    expect(res.body.post.author.username).toBe(user.username);
    expect(Array.isArray(res.body.post.comments)).toBe(true);
  });

  it('updates own post', async () => {
    const res = await request(app)
      .put(`/api/posts/${postId}`)
      .set('Authorization', `Bearer ${token}`)
      .send({ title: 'Updated' });
    expect(res.status).toBe(200);
    expect(res.body.post.title).toBe('Updated');
  });

  it('deletes own post', async () => {
    const res = await request(app)
      .delete(`/api/posts/${postId}`)
      .set('Authorization', `Bearer ${token}`);
    expect(res.status).toBe(204);
  });
});
