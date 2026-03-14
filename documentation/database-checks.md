# Database Checks And SQL

This file gives a few practical SQL commands for checking whether papers and embeddings have been written to Postgres.

Assumed connection:

- host: `127.0.0.1`
- port: `5432`
- user: `sa`
- password: `NHAN35`
- database: `NhanesLandingZone`
- schema: `epimind`

## Basic Checks

List schemas:

```sql
\dn
```

List `epimind` tables:

```sql
\dt epimind.*
```

## Project And Paper Inventory

```sql
select project_id, project_name, project_slug
from epimind.projects
order by project_name;
```

```sql
select paper_id, project_id, paper_name, paper_slug
from epimind.papers
order by paper_name;
```

## Chunk And Embedding Counts

```sql
select count(*) as chunk_count
from epimind.paper_chunks;
```

```sql
select count(*) as embedding_count
from epimind.chunk_embeddings;
```

## Check A Single Paper

```sql
select p.paper_id, p.paper_name, p.paper_slug
from epimind.papers p
where lower(p.paper_slug) = 'cobaltpaper';
```

```sql
select count(*) as chunk_count
from epimind.paper_chunks c
join epimind.papers p on p.paper_id = c.paper_id
where lower(p.paper_slug) = 'cobaltpaper';
```

```sql
select count(*) as embedding_count
from epimind.chunk_embeddings e
join epimind.paper_chunks c on c.chunk_id = e.chunk_id
join epimind.papers p on p.paper_id = c.paper_id
where lower(p.paper_slug) = 'cobaltpaper';
```

## Inspect Chunk Rows

```sql
select
  p.paper_name,
  s.section_name,
  c.chunk_id,
  c.chunk_index,
  left(c.text, 200) as chunk_preview
from epimind.paper_chunks c
join epimind.papers p on p.paper_id = c.paper_id
left join epimind.paper_sections s on s.section_id = c.section_id
where lower(p.paper_slug) = 'cobaltpaper'
order by c.chunk_id;
```

## Inspect Embedding Metadata

```sql
select
  p.paper_name,
  c.chunk_id,
  e.embedding_model,
  e.embedding_dimensions,
  e.embedded_at
from epimind.chunk_embeddings e
join epimind.paper_chunks c on c.chunk_id = e.chunk_id
join epimind.papers p on p.paper_id = c.paper_id
where lower(p.paper_slug) = 'cobaltpaper'
order by c.chunk_id;
```

## Combined Check

This is often the most useful quick diagnostic:

```sql
select
  p.paper_name,
  count(distinct c.chunk_id) as chunks,
  count(distinct e.chunk_id) as embeddings
from epimind.papers p
left join epimind.paper_chunks c on c.paper_id = p.paper_id
left join epimind.chunk_embeddings e on e.chunk_id = c.chunk_id
where lower(p.paper_slug) = 'cobaltpaper'
group by p.paper_name;
```

Interpretation:

- no row returned: the paper is not registered in `epimind.papers`
- chunks > 0 and embeddings = 0: chunk registration succeeded but embedding creation failed
- chunks > 0 and embeddings > 0: the paper is indexed
