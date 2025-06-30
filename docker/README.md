# ss2db Docker Test Environment

This Docker setup provides test instances of PostgreSQL and MySQL databases for developing and testing the ss2db application.

## Features

- **PostgreSQL 16** with persistent data storage
- **MySQL 8.0** with persistent data storage  
- **Adminer** web interface for database management
- **Pre-configured databases** with sample data
- **Health checks** and proper networking
- **Volume persistence** - data survives container restarts

## Quick Start

### Prerequisites
- Docker and Docker Compose installed
- Ports 3306, 5432, and 8080 available on your system

### Start the Services

```bash
# Navigate to the docker directory
cd docker

# Start all services (PostgreSQL, MySQL, and Adminer)
docker-compose up -d

# Check service status
docker-compose ps

# View logs
docker-compose logs -f
```

### Stop the Services

```bash
# Stop services but keep data
docker-compose down

# Stop services and remove volumes (WARNING: destroys data)
docker-compose down -v
```

## Service Details

### PostgreSQL
- **Host**: localhost
- **Port**: 5432
- **Database**: ss2db_test
- **Username**: ss2db_user
- **Password**: ss2db_password
- **Admin**: postgres (no password in development)

### MySQL
- **Host**: localhost  
- **Port**: 3306
- **Database**: ss2db_test
- **Username**: ss2db_user
- **Password**: ss2db_password
- **Root Password**: root_password

### Adminer (Database Web UI)
- **URL**: http://localhost:8080
- **Default Server**: postgres (can switch to mysql)

## Database Structure

Both databases are pre-configured with:

### Metadata Tables
- **export_logs**: Track ss2db export operations
- **column_mappings**: Store Smartsheet to database column mappings

### Sample Data Tables
- **smartsheet_123456789**: Sample task/project data (5 rows)
- **smartsheet_report_987654321**: Sample report data (3 rows)

## Connection Strings

### For ss2db Application

Create a `.env` file in the project root:

```bash
# PostgreSQL
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=ss2db_test
POSTGRES_USER=ss2db_user
POSTGRES_PASSWORD=ss2db_password

# MySQL
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_DB=ss2db_test
MYSQL_USER=ss2db_user
MYSQL_PASSWORD=ss2db_password
```

### Testing Database Connections

```bash
# Test PostgreSQL connection
psql -h localhost -p 5432 -U ss2db_user -d ss2db_test

# Test MySQL connection  
mysql -h localhost -P 3306 -u ss2db_user -pss2db_password ss2db_test
```

## Development Usage

### Running ss2db Against Test Databases

```bash
# Test PostgreSQL export (dry run)
ss2db --sheet-id 123456789 --db-type postgresql --dry-run --verbose

# Test MySQL export (dry run)
ss2db --sheet-id 123456789 --db-type mysql --dry-run --verbose

# Generate PostgreSQL script from sample data
ss2db --sheet-id 123456789 --db-type postgresql --skip-extraction --skip-schema
```

### Viewing Sample Data

Use Adminer at http://localhost:8080 or connect directly:

```sql
-- PostgreSQL - View sample data
SELECT * FROM public.smartsheet_123456789;
SELECT * FROM smartsheet.export_logs;

-- MySQL - View sample data  
SELECT * FROM smartsheet_123456789;
SELECT * FROM export_logs;
```

## Data Persistence

Data is stored in Docker named volumes:
- **ss2db_postgres_data**: PostgreSQL data
- **ss2db_mysql_data**: MySQL data

### Backup Data

```bash
# Backup PostgreSQL
docker exec ss2db-postgres pg_dump -U ss2db_user ss2db_test > backup_postgres.sql

# Backup MySQL
docker exec ss2db-mysql mysqldump -u ss2db_user -pss2db_password ss2db_test > backup_mysql.sql
```

### Restore Data

```bash
# Restore PostgreSQL
docker exec -i ss2db-postgres psql -U ss2db_user ss2db_test < backup_postgres.sql

# Restore MySQL
docker exec -i ss2db-mysql mysql -u ss2db_user -pss2db_password ss2db_test < backup_mysql.sql
```

## Troubleshooting

### Port Conflicts
If ports are in use, modify the port mappings in `docker-compose.yml`:

```yaml
ports:
  - "15432:5432"  # PostgreSQL on port 15432
  - "13306:3306"  # MySQL on port 13306
  - "18080:8080"  # Adminer on port 18080
```

### Reset Everything
```bash
# Stop and remove all containers, networks, and volumes
docker-compose down -v

# Remove any orphaned containers
docker system prune -f

# Start fresh
docker-compose up -d
```

### View Container Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f postgres
docker-compose logs -f mysql
docker-compose logs -f adminer
```

### Connect to Container Shell
```bash
# PostgreSQL container
docker exec -it ss2db-postgres bash

# MySQL container
docker exec -it ss2db-mysql bash
```

## Configuration Files

- `docker-compose.yml`: Main service configuration
- `.env`: Environment variables for Docker Compose
- `postgres/init.sql`: PostgreSQL initialization
- `postgres/sample_data.sql`: PostgreSQL sample data
- `mysql/init.sql`: MySQL initialization  
- `mysql/sample_data.sql`: MySQL sample data
- `mysql/mysql.cnf`: MySQL configuration

## Security Notes

⚠️ **Development Only**: These configurations are for development/testing only. Do not use in production without proper security hardening:

- Change default passwords
- Restrict network access
- Enable SSL/TLS
- Configure proper user permissions
- Use secrets management