# Knicks vs Spurs Matchup Projector

I just wanted something small to tinker with while the Finals were on, so here it is: a single web page that grabs the actual Knicks vs Spurs games from this season and takes a guess at how the next one might go. Nothing serious, just a fun way to stare at numbers between possessions.

**Live page:** https://exekyute.github.io/knicks-spurs-matchup-projector/

## What it does

Open the page and you get every completed Knicks vs Spurs game this season, the head to head record, and each team's scoring average. Then it projects the next meeting: a score line, who's favored, and a rough win %. There's also a little chart that plays the next game out thousands of times to show the spread of possible outcomes.

The next game's host is filled in straight from the schedule, so home court edge is already baked in.

## The "projection", loosely

Nothing crazy. It takes the past games, leans a bit more on the recent ones if you want (there is a slider for that), and works out an average score and a typical margin. From there it figures the odds and runs a Monte Carlo simulation, which is just a fancy way of saying it rolls the dice on the game a few thousand times and counts how often each team comes out ahead. It is a tiny sample of games, so take the percentages with a grain of salt.

## Where the data comes from

It pulls live from ESPN's public API every time the page loads, leading scorers and all. That also means new playoff games show up on their own once they go final, so the projection keeps pace with the series. If the connection is having a bad day, it quietly falls back to a saved snapshot and tells you that is what you are looking at.

## Running it

Just open the live page above. It is hosted on GitHub Pages, and you need an internet connection for the live data to load.

## License

MIT. Do whatever you want with it.
