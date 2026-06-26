// Entry point. Imports the app and starts listening.

const app = require('./app');

const PORT = process.env.PORT || 3000;

app.listen(PORT, () => {
  console.log(`Blog API listening on port ${PORT}`);
});
