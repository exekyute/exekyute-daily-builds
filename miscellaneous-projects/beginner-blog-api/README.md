# Blog API

[![Node](https://img.shields.io/badge/Node-%E2%89%A518-D52B1E?style=for-the-badge&logo=node.js&logoColor=white)](https://nodejs.org)
[![Express](https://img.shields.io/badge/Express-4.x-003E7E?style=for-the-badge&logo=express&logoColor=white)](https://expressjs.com)
[![Prisma](https://img.shields.io/badge/Prisma-5.x-003E7E?style=for-the-badge&logo=prisma&logoColor=white)](https://www.prisma.io)
[![License](https://img.shields.io/badge/license-MIT-FFC72C?style=for-the-badge)](LICENSE)

A beginner follow-along project to explore backend development. This is my first time building a real backend, so the goal here is learning the moving parts (HTTP, auth, a relational database, deployment) rather than shipping a polished product.

**Live API:** https://beginner-blog-api.onrender.com

## What it does

A small REST API for a blog platform:
- Users can register and log in (JWT auth, bcrypt-hashed passwords)
- Authenticated users can create, edit, and delete their own posts
- Anyone can read posts and comments
- Authenticated users can leave comments on any post

## Tech stack

- Node.js with Express for the HTTP server
- PostgreSQL hosted on Neon
- Prisma ORM for queries and migrations
- JWT for stateless auth, bcrypt for password hashing
- Zod for request body validation
- Jest with Supertest for tests
- Deployed on Render

## Schema

Three tables, two relationships.

**User** holds account info. Each user owns many posts and many comments. The password is never stored as plain text, only as a bcrypt hash.

**Post** belongs to one user (the author). Each post can have many comments. Deleting a user cascades to delete their posts.

**Comment** belongs to one post and one user. Deleting a post cascades to delete its comments.

All primary keys are UUIDs rather than auto-increment integers, which is safer for a public API (no sequential ID guessing).

The full schema lives in [prisma/schema.prisma](prisma/schema.prisma).

## Endpoints

Base URL: `/api`. All bodies are JSON. Authenticated routes need `Authorization: Bearer <token>`.

### Auth
| Method | Path             | Body                              |
|--------|------------------|-----------------------------------|
| POST   | `/auth/register` | `{ email, username, password }`   |
| POST   | `/auth/login`    | `{ email, password }`             |

### Posts
| Method | Path           | Auth     | Notes                            |
|--------|----------------|----------|----------------------------------|
| GET    | `/posts`       | public   | Supports `?page=1&limit=10`      |
| GET    | `/posts/:id`   | public   | Returns the post with comments   |
| POST   | `/posts`       | required | Body: `{ title, content }`       |
| PUT    | `/posts/:id`   | owner    | Body: `{ title?, content? }`     |
| DELETE | `/posts/:id`   | owner    | Returns 204                      |

### Comments
| Method | Path                          | Auth     |
|--------|-------------------------------|----------|
| GET    | `/posts/:postId/comments`     | public   |
| POST   | `/posts/:postId/comments`     | required |
| DELETE | `/comments/:id`               | owner    |

Errors always return the same shape:
```json
{ "error": { "message": "Post not found", "status": 404 } }
```

## Project structure

```
src/
  config/      Prisma client singleton
  controllers/ Request handlers, one file per resource
  middleware/  auth, validation, error handler
  routes/      URL to controller wiring
  utils/       async error wrapper
  app.js       Express setup (importable for tests)
  server.js    Entry point
prisma/
  schema.prisma
  seed.js
tests/
```

## Running it locally

You'll need Node 18+, a PostgreSQL database (a free Neon project works great), and a JWT secret.

```bash
git clone https://github.com/exekyute/beginner-blog-api.git
cd beginner-blog-api
npm install

cp .env.example .env
# Fill in DATABASE_URL and JWT_SECRET in .env

npx prisma migrate dev --name init
npm run prisma:seed   # optional, adds fake data

npm run dev
```

The server prints `Blog API listening on port 3000`. Visit `http://localhost:3000/api/posts` to see seeded data.

## Tests

```bash
npm test
```

Uses Supertest to drive the Express app directly. The tests hit a real database, so point `DATABASE_URL` at a separate test database if you want to keep test data out of your dev database.

## Things I learned

- How HTTP routes map to controller functions in Express, and why middleware order matters
- Prisma's schema-first workflow (write the schema, generate the client, run migrations)
- Why password hashing and JWT signing live in separate concerns (bcrypt for storage, JWT for transport)
- How to structure a Node project so routes, business logic, and database access stay separate
- How to deploy a Node app with a managed Postgres database without touching a server

## License

MIT. See [LICENSE](LICENSE).
