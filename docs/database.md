# Database and migrations

The backend supports PostgreSQL outside AWS. RDS is a hosting choice, not an application requirement. Configure the endpoint, credentials, network access and provider-required SSL settings.

For host development:

```env
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST:5432/DBNAME?sslmode=require
```

Compose injects its local DB URL, and the bundled AWS template injects RDS settings. Change those deployment settings as well when choosing another PostgreSQL server. Migration uses the same backend connection settings.

## A concrete example

Initially, `links.code` allowed eight characters:

```sql
code VARCHAR(8)
```

Custom endings such as `my-portfolio` need more space. The model now describes `String(64)`, and migration `0002` changes the real column to `VARCHAR(64)` without replacing existing links.

```text
0001: create initial tables
0002: widen the short-code column
```

These are application migration IDs, not PostgreSQL engine versions. `down_revision` defines the predecessor. Running `alembic upgrade head` checks the current database's migration version and applies the missing steps.

Changing a model alone does not change a running database. Review a new migration and apply it before starting code that needs its new columns. Adding/editing a user or link is a normal data write, not a schema migration.

Do not rewrite migration files already applied to a shared database; add a new migration. Historical migrations still contain the original tables. The unused daily statistics table is retained for compatibility, while current statistics read click_events directly.

Migration prepares structure; it does not transfer records between database servers. To move existing data, back up and restore it separately. Never point integration tests at your application database.

## Tools

| Purpose | This Python app | TypeScript alternative |
| --- | --- | --- |
| Store data | PostgreSQL | PostgreSQL |
| Read/write from code | SQLAlchemy | Prisma ORM |
| Evolve table structure | Alembic | Prisma migration tools |

References: [Alembic tutorial](https://alembic.sqlalchemy.org/en/latest/tutorial.html), [SQLAlchemy database URLs](https://docs.sqlalchemy.org/en/20/core/engines.html#database-urls), [Prisma ORM](https://www.prisma.io/docs/orm).
