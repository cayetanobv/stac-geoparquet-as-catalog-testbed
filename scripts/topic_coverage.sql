-- How much of a topic sits under the groups a walk chose. A collection belongs to the topic when its title or one of
-- its keywords contains a term, without case or accents, as walk_timing.py matches group titles.
-- usage: duckdb -c "SET VARIABLE u='indexes/berlin-geoportal/collections.parquet'; SET VARIABLE lon=13.405; SET VARIABLE lat=52.52; SET VARIABLE terms=['verkehr','mobilit']; SET VARIABLE groups=['verkehr','mobilitaet'];" -c ".read scripts/topic_coverage.sql"
LOAD spatial;
CREATE TEMP TABLE topic AS
SELECT id, parents[2] AS grp, ST_Intersects(geometry, ST_Point(getvariable('lon'), getvariable('lat'))) AS at_point
FROM read_parquet(getvariable('u'))
WHERE len(list_filter(getvariable('terms'), lambda t: strip_accents(lower(title)) LIKE '%' || t || '%'
                      OR len(list_filter(keywords, lambda k: strip_accents(lower(k)) LIKE '%' || t || '%')) > 0)) > 0;
SELECT count(*) AS topic, count(*) FILTER (WHERE list_contains(getvariable('groups'), grp)) AS under_chosen_groups,
       count(*) FILTER (WHERE at_point) AS topic_at_point,
       count(*) FILTER (WHERE at_point AND list_contains(getvariable('groups'), grp)) AS at_point_under_chosen_groups
FROM topic;
SELECT grp, count(*) AS topic, count(*) FILTER (WHERE at_point) AS topic_at_point,
       list_contains(getvariable('groups'), grp) AS chosen
FROM topic GROUP BY ALL ORDER BY topic DESC;
