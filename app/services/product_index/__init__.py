"""
The internal Product Index: VisualFind's own product catalog, populated
automatically from products the app has already discovered via searches.

- `embedding_backends/` defines the pluggable model interface
  (`EmbeddingBackend`) plus the default lightweight backend, and a
  registry for looking backends up by name.
- `embedding_service.EmbeddingService` is the Embedding Service: given a
  product, it downloads the image, generates an embedding via whichever
  backend is configured, stores it on the entry, and skips all of that if
  the entry already has a current embedding.
- `service` owns the catalog itself: upserting products (which triggers
  embedding for new products), listing/searching it, finding
  visually-similar products, and backfilling embeddings for rows that
  don't have a current one.

Phase 1 moved VisualFind from "hit Google Lens fresh every time and throw
the results away" to "build and query a real internal product index".
Phase 2 made that index self-embedding: every new product is embedded
automatically, embeddings are never recomputed unnecessarily, and the
model doing the embedding is swappable behind one service.
"""
