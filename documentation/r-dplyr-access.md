# R And dplyr Access

This file shows how to access the `epimind` tables from R.

If you already use the local `phonto` package, also see:

- [phonto And DB Access](/Users/robert/Projects/Epiconnector/EpiconUI/documentation/phonto-db-access.md)

## Packages

```r
install.packages(c("DBI", "RPostgres", "dplyr", "dbplyr", "readr"))
```

## Connect To Postgres

```r
library(DBI)
library(RPostgres)
library(dplyr)
library(dbplyr)

con <- dbConnect(
  RPostgres::Postgres(),
  host = "127.0.0.1",
  port = 5432,
  user = "sa",
  password = "NHAN35",
  dbname = "NhanesLandingZone"
)
```

This direct `DBI` connection is the simplest way to query the `epimind` paper tables.

## Reference Tables

```r
projects_tbl <- tbl(con, in_schema("epimind", "projects"))
papers_tbl <- tbl(con, in_schema("epimind", "papers"))
sections_tbl <- tbl(con, in_schema("epimind", "paper_sections"))
chunks_tbl <- tbl(con, in_schema("epimind", "paper_chunks"))
embeddings_tbl <- tbl(con, in_schema("epimind", "chunk_embeddings"))
```

This is the recommended pattern for the `epimind` schema, even if you are also using `phonto` for NHANES-side access.

## List Projects And Papers

```r
projects_tbl %>%
  select(project_id, project_name, project_slug) %>%
  arrange(project_name) %>%
  collect()
```

```r
papers_tbl %>%
  select(paper_id, project_id, paper_name, paper_slug) %>%
  arrange(paper_name) %>%
  collect()
```

## Pull Chunks For One Paper

```r
paper_chunks <- papers_tbl %>%
  filter(tolower(paper_slug) == "cobaltpaper") %>%
  inner_join(chunks_tbl, by = "paper_id") %>%
  select(paper_name, chunk_id, chunk_index, text, markdown) %>%
  arrange(chunk_index) %>%
  collect()
```

## Pull Sections And Chunks Together

```r
paper_sections <- papers_tbl %>%
  filter(tolower(paper_slug) == "cobaltpaper") %>%
  inner_join(chunks_tbl, by = "paper_id") %>%
  left_join(sections_tbl, by = c("paper_id", "section_id")) %>%
  select(paper_name, section_name, chunk_index, text) %>%
  arrange(section_name, chunk_index) %>%
  collect()
```

## Count Embeddings Per Paper

```r
paper_embedding_counts <- papers_tbl %>%
  left_join(chunks_tbl, by = "paper_id") %>%
  left_join(embeddings_tbl, by = "chunk_id") %>%
  group_by(paper_name, paper_slug) %>%
  summarise(
    chunks = n_distinct(chunk_id),
    embeddings = n_distinct(chunk_id[!is.na(embedding_model)]),
    .groups = "drop"
  ) %>%
  arrange(paper_name) %>%
  collect()
```

## Pull Asset Paths

```r
assets_tbl <- tbl(con, in_schema("epimind", "paper_assets"))

paper_assets <- papers_tbl %>%
  filter(tolower(paper_slug) == "cobaltpaper") %>%
  inner_join(assets_tbl, by = "paper_id") %>%
  select(paper_name, asset_type, relative_path, absolute_path) %>%
  arrange(asset_type) %>%
  collect()
```

## Mix NHANES Queries With Paper Queries

One practical pattern is:

1. use `phonto` to pull NHANES data and metadata
2. use `DBI` / `dbplyr` directly for `epimind.*`
3. join or compare the results in R after `collect()`

## Work With Local `~/.EpiMind` Metadata In R

You can combine DB access with the local JSON metadata files:

```r
library(readr)
library(jsonlite)

paper_json <- "~/.EpiMind/Projects/my-project/papers/cobaltpaper/paper.json"
paper_meta <- jsonlite::fromJSON(paper_json)

paper_meta$rag
paper_meta$manifest
```

This is useful if you want to:

- read local chunk or markdown files directly
- discover the DB IDs already assigned to the paper
- confirm which embedding model and schema were used

## Close The Connection

```r
dbDisconnect(con)
```
