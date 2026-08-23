-- TenSura World Database: analytical queries
--
-- Each query is one block. A block starts with a "--#" line that names the
-- question it answers; everything until the next "--#" is one SQL statement.
-- engine/run_queries.py reads this file, runs each block against the database,
-- and prints the results. You can also paste any single block into the sqlite3
-- shell.

--# How many characters fall into each race category
SELECT r.category AS race_category,
       COUNT(*)   AS characters
FROM characters c
JOIN races r ON r.race_id = c.race_id
GROUP BY r.category
ORDER BY characters DESC, race_category;

--# Each nation's roster size and its standing with Tempest
SELECT n.name                AS nation,
       n.relation_to_tempest AS relation,
       COUNT(c.character_id)  AS members
FROM nations n
LEFT JOIN characters c ON c.nation_id = n.nation_id
GROUP BY n.nation_id, n.name, n.relation_to_tempest
ORDER BY members DESC, nation;

--# The strongest characters by wiki-cited Existence Points
SELECT RANK() OVER (ORDER BY c.ep_estimate DESC) AS rank,
       c.name        AS character,
       c.threat_rank AS threat_rank,
       c.ep_estimate AS existence_points
FROM characters c
WHERE c.ep_estimate IS NOT NULL
ORDER BY c.ep_estimate DESC;

--# How the skills break down by tier
SELECT s.skill_type,
       COUNT(*) AS skills
FROM skills s
GROUP BY s.skill_type
ORDER BY skills DESC, s.skill_type;

--# Characters who carry the most skills
SELECT c.name        AS character,
       r.name        AS race,
       COUNT(cs.skill_id) AS skills
FROM characters c
JOIN races r ON r.race_id = c.race_id
JOIN character_skills cs ON cs.character_id = c.character_id
GROUP BY c.character_id, c.name, r.name
HAVING skills >= 2
ORDER BY skills DESC, character
LIMIT 10;

--# Who climbed the longest evolution ladder
SELECT c.name AS character,
       COUNT(e.evolution_id) AS evolution_steps,
       GROUP_CONCAT(e.to_form, ' -> ') AS became
FROM characters c
JOIN evolutions e ON e.character_id = c.character_id
GROUP BY c.character_id, c.name
ORDER BY evolution_steps DESC, character
LIMIT 10;

--# The Octagram: the eight sitting demon lords
SELECT c.name        AS demon_lord,
       dl.title      AS title,
       CASE dl.is_awakened WHEN 1 THEN 'Awakened' ELSE 'Not awakened' END AS awakening,
       c.ep_estimate AS existence_points
FROM demon_lords dl
JOIN characters c ON c.character_id = dl.character_id
WHERE dl.roster = 'Octagram'
ORDER BY c.ep_estimate IS NULL, c.ep_estimate DESC, demon_lord;

--# The four True Dragons in birth order
SELECT td.birth_order,
       c.name    AS dragon,
       td.epithet,
       td.element,
       td.status
FROM true_dragons td
JOIN characters c ON c.character_id = td.character_id
ORDER BY td.birth_order;

--# Faction sizes, largest first
SELECT f.name         AS faction,
       f.aligned_with AS aligned_with,
       COUNT(cf.character_id) AS members
FROM factions f
JOIN character_factions cf ON cf.faction_id = f.faction_id
GROUP BY f.faction_id, f.name, f.aligned_with
ORDER BY members DESC, faction;

--# Character debuts per arc, with a running total across the story
WITH per_arc AS (
    SELECT a.sequence_no,
           a.name AS arc,
           COUNT(c.character_id) AS debuts
    FROM arcs a
    LEFT JOIN characters c ON c.debut_arc_id = a.arc_id
    GROUP BY a.arc_id, a.sequence_no, a.name
)
SELECT sequence_no,
       arc,
       debuts,
       SUM(debuts) OVER (ORDER BY sequence_no) AS cumulative_cast
FROM per_arc
ORDER BY sequence_no;

--# Average Existence Points by threat rank, among ranks that have figures
SELECT c.threat_rank,
       COUNT(c.ep_estimate)              AS with_ep,
       ROUND(AVG(c.ep_estimate))         AS avg_existence_points
FROM characters c
WHERE c.ep_estimate IS NOT NULL
GROUP BY c.threat_rank
ORDER BY avg_existence_points DESC;
