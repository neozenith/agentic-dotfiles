# Programming Language & Framework Node Reference

Logo icons for languages, frameworks, and runtimes from `diagrams.programming.*`.

## Languages

```python
from diagrams.programming.language import (
    Bash, C, Cpp, Csharp, Dart, Elixir, Erlang, Go, Java,
    Javascript,   # alias: JavaScript
    Kotlin, Latex, Matlab,
    Nodejs,       # alias: NodeJS
    Php,          # alias: PHP
    Python, R, Ruby, Rust, Scala, Sql, Swift,
    Typescript,   # alias: TypeScript
)
```

## Frameworks

```python
from diagrams.programming.framework import (
    Angular, Backbone, Camel, Django,
    Dotnet,    # alias: DotNet
    Ember,
    Fastapi,   # alias: FastAPI
    Flask, Flutter,
    Graphql,   # alias: GraphQL
    Hibernate, Jhipster, Laravel, Micronaut,
    Nextjs,    # alias: NextJs
    Phoenix, Quarkus, Rails, React, Spring,
    Sqlpage, Starlette, Svelte, Vercel, Vue,
)
```

## Runtimes

```python
from diagrams.programming.runtime import Dapr
```

## Example: Tech Stack Diagram

```python
from diagrams.programming.language import Python, Typescript
from diagrams.programming.framework import React, FastAPI
from diagrams.aws.compute import Lambda
from diagrams.aws.database import Dynamodb

react = React("Frontend")
api = FastAPI("API")
worker = Lambda("Worker")
db = Dynamodb("Store")

react >> api >> worker >> db
```
