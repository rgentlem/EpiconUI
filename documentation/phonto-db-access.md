# phonto And DB Access

`phonto` already gives you a good R-side access layer for the NHANES tables in `NhanesLandingZone`. The main point for `EpiconUI` is:

- use `phonto` for NHANES data and metadata access
- use direct `DBI` / `dbplyr` access for the `epimind` schema that stores projects, papers, chunks, and embeddings

This matches how `phonto` is implemented.

## What `phonto` Is Doing

Inside the package, `phonto` uses the `nhanesA` connection helper and a `dplyr`/`dbplyr` pattern like:

```r
dplyr::tbl(cn(), I(MetadataTable("QuestionnaireDescriptions")))
```

and

```r
dplyr::tbl(cn(), I(tb_name))
```

You can see that in:

- `/Users/robert/Projects/Epiconnector/phonto/R/query_data.R`
- `/Users/robert/Projects/Epiconnector/phonto/R/qc-codebook.R`

The important practical point is that the package is already built around lazy database queries with `dplyr::tbl(...)`.

## Recommended Public Interface

For NHANES-side work, prefer the exported `phonto` functions instead of reaching into its internals.

Examples:

```r
library(phonto)

metadata_var(variable = "RIDAGEYR")
metadata_tab(table = "DEMO_J")
```

```r
library(phonto)

unionQuery(
  list(
    DEMO_I = c("RIDAGEYR", "RIAGENDR"),
    DEMO_J = c("RIDAGEYR", "RIAGENDR")
  )
)
```

```r
library(phonto)

jointQuery(
  list(
    DEMO_J = c("RIDAGEYR", "RIAGENDR"),
    BPQ_J = c("BPQ020", "BPQ050A")
  )
)
```

These functions are a good fit for:

- table discovery
- metadata lookup
- simple multi-table NHANES joins across cycles

## Accessing `epimind` Tables Alongside `phonto`

`phonto` is aimed at NHANES content, not the new paper/RAG schema. For `epimind.*`, use `DBI` and `dbplyr` directly.

```r
library(DBI)
library(RPostgres)
library(dplyr)
library(dbplyr)
library(phonto)
```

```r
con <- dbConnect(
  RPostgres::Postgres(),
  host = "127.0.0.1",
  port = 5432,
  user = "sa",
  password = "NHAN35",
  dbname = "NhanesLandingZone"
)
```

```r
papers_tbl <- tbl(con, in_schema("epimind", "papers"))
chunks_tbl <- tbl(con, in_schema("epimind", "paper_chunks"))
embeddings_tbl <- tbl(con, in_schema("epimind", "chunk_embeddings"))
```

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
  collect()
```

## Example Workflow: NHANES + Paper Metadata

Use `phonto` to get NHANES metadata:

```r
library(phonto)

bpq_meta <- metadata_var(variable = c("BPQ020", "BPQ050A"), table = "BPQ_J")
```

Then use `epimind` tables to inspect the paper chunks:

```r
paper_chunks <- papers_tbl %>%
  filter(tolower(paper_slug) == "cobaltpaper") %>%
  inner_join(chunks_tbl, by = "paper_id") %>%
  select(paper_name, chunk_index, text) %>%
  arrange(chunk_index) %>%
  collect()
```

Now both objects are in R and can be combined in ordinary `dplyr` code or passed into later analysis functions.

## If You Want The phonto Style For `epimind`

The relevant style is not a special package feature, it is the pattern:

```r
dplyr::tbl(connection, I("schema.table"))
```

For example:

```r
tbl(con, I("epimind.papers")) %>%
  select(paper_id, paper_name, paper_slug) %>%
  collect()
```

That is the closest analogue to what `phonto` does internally for NHANES tables.

## Suggested Division Of Responsibility

- `phonto`: NHANES metadata, table lookup, and cross-cycle query helpers
- `EpiconUI` / `epimind`: projects, uploaded papers, chunks, embeddings, and paper-linked provenance

That keeps each layer doing what it is already designed for.
