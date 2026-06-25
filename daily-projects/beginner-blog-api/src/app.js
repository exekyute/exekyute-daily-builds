// Builds the Express app. Kept separate from server.js so tests can import
// it without starting a real network listener.

const express = require('express');
const cors = require('cors');
require('dotenv').config();

const authRoutes = require('./routes/authRoutes');
const postRoutes = require('./routes/postRoutes');
const {
  postScoped: postCommentRoutes,
  flat: commentRoutes,
} = require('./routes/commentRoutes');
const { errorHandler, notFound } = require('./middleware/errorHandler');

const app = express();

app.use(cors());
app.use(express.json());

app.get('/', (req, res) => {
  res.json({ name: 'Blog API', status: 'running' });
});

app.use('/api/auth', authRoutes);
app.use('/api/posts', postRoutes);
app.use('/api/posts/:postId/comments', postCommentRoutes);
app.use('/api/comments', commentRoutes);

// Order matters: notFound catches anything unmatched, errorHandler is last.
app.use(notFound);
app.use(errorHandler);

module.exports = app;
