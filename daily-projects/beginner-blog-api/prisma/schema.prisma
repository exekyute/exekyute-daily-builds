// Prisma schema: the single source of truth for the database.
// After editing, run `npx prisma migrate dev --name <change>` to generate SQL.

generator client {
  provider = "prisma-client-js"
}

datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
}

model User {
  id           String    @id @default(uuid())
  email        String    @unique
  username     String    @unique
  // Stored as a bcrypt hash. The plain password never reaches the database.
  passwordHash String
  createdAt    DateTime  @default(now())

  posts        Post[]
  comments     Comment[]
}

model Post {
  id        String    @id @default(uuid())
  title     String
  content   String
  createdAt DateTime  @default(now())
  updatedAt DateTime  @updatedAt

  authorId  String
  // onDelete: Cascade -- deleting a user removes their posts automatically.
  author    User      @relation(fields: [authorId], references: [id], onDelete: Cascade)

  comments  Comment[]

  @@index([authorId])
  @@index([createdAt])
}

model Comment {
  id        String   @id @default(uuid())
  content   String
  createdAt DateTime @default(now())

  postId    String
  post      Post     @relation(fields: [postId], references: [id], onDelete: Cascade)

  authorId  String
  author    User     @relation(fields: [authorId], references: [id], onDelete: Cascade)

  @@index([postId])
  @@index([authorId])
}
