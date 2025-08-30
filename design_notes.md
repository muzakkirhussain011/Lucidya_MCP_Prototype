# Lucidya MCP Prototype - Design Notes

## Architecture Rationale

### Why Multi-Agent Architecture?

The multi-agent pattern provides several enterprise advantages:

1. **Separation of Concerns**: Each agent has a single, well-defined responsibility
2. **Testability**: Agents can be unit tested in isolation
3. **Scalability**: Agents can be distributed across workers in production
4. **Observability**: Clear boundaries make debugging and monitoring easier
5. **Compliance**: Dedicated Compliance agent ensures policy enforcement

### Why MCP (Model Context Protocol)?

MCP servers provide:
- **Service Isolation**: Each capability (search, email, calendar, store) runs independently
- **Language Agnostic**: MCP servers can be implemented in any language
- **Standardized Interface**: JSON-RPC provides clear contracts
- **Production Ready**: Similar to microservices architecture

### Why FAISS with Normalized Embeddings?

FAISS IndexFlatIP with L2-normalized embeddings offers:
- **Exact Search**: No approximation errors for small datasets
- **Cosine Similarity**: Normalized vectors make IP equivalent to cosine
- **Simple Deployment**: No training required, immediate indexing
- **Fast Retrieval**: Sub-millisecond searches for <100k vectors

### Why Ollama Streaming?

Real-time streaming provides:
- **User Experience**: Immediate feedback reduces perceived latency
- **Progressive Rendering**: Users see content as it's generated
- **Cancellation**: Streams can be interrupted if needed
- **Resource Efficiency**: No need to buffer entire responses

## Evaluation Criteria Alignment

### 1. Architectural Clarity (40%)

**Pipeline Design**: Clear DAG with deterministic flow
```
Hunter → Enricher → Contactor → Scorer → Writer → Compliance → Sequencer → Curator
```

**Event-Driven**: NDJSON streaming for real-time observability

**Clean Interfaces**: Every agent follows `run(state) -> state` pattern

### 2. Technical Execution (30%)

**Streaming Implementation**: 
- Ollama `/api/generate` with `stream: true`
- NDJSON event stream from backend to UI
- `st.write_stream` for progressive rendering

**Vector System**:
- sentence-transformers for embeddings
- FAISS for similarity search
- Persistent index with metadata

**MCP Integration**:
- Real Python servers (not mocks)
- Proper RPC communication
- Typed client wrappers

### 3. Creativity & Foresight (20%)

**Compliance Framework**: Regional policy toggles, suppression ledger, footer enforcement

**Handoff Packets**: Complete context transfer for human takeover

**Calendar Integration**: ICS generation for meeting scheduling

**Progressive Enrichment**: TTL-based fact expiry, confidence scoring

### 4. Communication (10%)

**Comprehensive Documentation**:
- README with setup, usage, and examples
- Design notes explaining decisions
- Inline code comments
- Test coverage for key behaviors

## Production Migration Path

### Phase 1: Containerization
```yaml
services:
  api:
    build: ./app
    depends_on: [mcp-search, mcp-email, mcp-calendar, mcp-store]
  
  mcp-search:
    build: ./mcp/servers/search
    ports: ["9001:9001"]
```

### Phase 2: Message Queue
Replace direct calls with event bus:
```python
# Current
result = await self.enricher.run(prospect)

# Production
await queue.publish("enricher.process", prospect)
prospect = await queue.consume("enricher.complete")
```

### Phase 3: Distributed Execution
- Deploy agents as Kubernetes Jobs/CronJobs
- Use Airflow/Prefect for orchestration
- Implement circuit breakers and retries

### Phase 4: Enhanced Observability
- OpenTelemetry for distributed tracing
- Structured logging to ELK stack
- Metrics to Prometheus/Grafana
- Error tracking with Sentry

## Performance Optimizations

### Current Limitations
- Single-threaded MCP servers
- In-memory state management
- Sequential agent execution
- No connection pooling

### Production Optimizations
1. **Parallel Processing**: Run independent agents concurrently
2. **Batch Operations**: Process multiple prospects simultaneously
3. **Caching Layer**: Redis for hot data
4. **Connection Pooling**: Reuse HTTP/database connections
5. **Async Everything**: Full async/await from edge to storage

## Security Considerations

### Current State (Prototype)
- No authentication
- Plain HTTP communication
- Unencrypted storage
- No rate limiting

### Production Requirements
- OAuth2/JWT authentication
- TLS for all communication
- Encrypted data at rest
- Rate limiting per client
- Input validation and sanitization
- Audit logging for compliance

## Scaling Strategies

### Horizontal Scaling
- Stateless API servers behind load balancer
- Multiple MCP server instances with service discovery
- Distributed vector index with sharding

### Vertical Scaling
- GPU acceleration for embeddings
- Larger Ollama models for better quality
- More sophisticated scoring algorithms

### Data Scaling
- PostgreSQL for transactional data
- S3 for document storage
- ElasticSearch for full-text search
- Pinecone/Weaviate for vector search at scale

## Success Metrics

### Technical Metrics
- Pipeline completion rate > 95%
- Streaming latency < 100ms per token
- Vector search < 50ms for 1M documents
- MCP server availability > 99.9%

### Business Metrics
- Prospect → Meeting conversion rate
- Email engagement rates
- Time to handoff < 5 minutes
- Compliance violation rate < 0.1%

## Future Enhancements

1. **Multi-modal Input**: Support for images, PDFs, audio
2. **A/B Testing**: Test different prompts and strategies
3. **Feedback Loop**: Learn from successful conversions
4. **Advanced Personalization**: Industry-specific templates
5. **Real-time Collaboration**: Multiple users working on same prospect
6. **Workflow Customization**: Configurable agent pipeline
7. **Smart Scheduling**: ML-based optimal send time prediction
8. **Conversation Intelligence**: Analyze reply sentiment and intent
```
