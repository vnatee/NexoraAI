# Knowledge metadata profiles

NexoraAI uses a hybrid metadata model. Security context is derived by the server, while reusable business fields are defined by a Team metadata profile.

## Security-derived core

The uploader cannot override these values:

- Team and Data Group ownership
- Data Group exposure and publication state
- derived Audience (`internal` or `external`)
- source file, upload actor and ingestion timestamps
- metadata profile ID and pinned profile version

Metadata is descriptive. It never grants document access, bypasses personal/team/global ACLs, or publishes an External Data Group.

## Product Knowledge profile

Team managers can create the built-in Product Knowledge profile from Team Knowledge upload. It includes:

- product family and model
- brand
- document type
- language
- document version
- lifecycle status
- effective date
- search keywords

Required fields are validated by both the browser and server. An upload routed to any External Data Group must select a metadata profile.

Each ingestion job stores a normalized metadata snapshot plus the profile ID and version. Editing a profile later therefore does not reinterpret an already indexed document.

## Search storage

Business values are stored in provider-neutral fields:

- `metadataProfileId` and `metadataProfileVersion` for governance/filtering
- `businessMetadata` as normalized `key=value` pairs
- `businessMetadataText` as searchable text, including the server-derived Audience

This fixed search schema works with Azure AI Search and the local Qdrant adapter without creating a new index field for every customer-specific attribute.

## Recommended extension

The current UI provisions the governed Product Knowledge template. A later profile designer can add versioned custom profiles using the same field model (`text`, `keyword`, `number`, `date`, `boolean`, and `enum`) with an approval workflow. Core security metadata must remain immutable.
