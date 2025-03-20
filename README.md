# Estate Code Generator

This monorepo contains multiple services and packages, organized for efficient development and management. The project is set up to use Docker Compose for local development.

## Requirements

You will need the following installed in your machine to be able to run this project:

> docker (https://docs.docker.com/engine/install/)

## Project Structure

```
├── docker-compose.yml       # Docker Compose file for local development
├── services/                # Contains service modules
│   ├── service_1/
│   └── service_2/
└── packages/                # Contains reusable Python packages
    ├── package_1/
    └── package_2/
```

### Folders

- **services/**: Each folder inside this directory represents an individual service. These are standalone Python service modules.
- **packages/**: Contains shared Python packages that are reusable across services.

### Docker Compose

The `docker-compose.yml` file in the root of the project is used to spin up the development environment, including all necessary services and their dependencies.

To build the environment, run:

```bash
make build
```

This will build and start all services in the `services/` folder and their required dependencies.

To clean the environment, run:

```bash
make clean
```

This will stop all docker containers and remove hanging images and volumes.

To run clean and build the project and start the services:

```bash
make clean build
```

To start the compose-stack, run:

```bash
make start
```

This will start all docker containers within the compose-stack.

To stop the compose-stack, run:

```bash
make stop
```

This will stop all docker containers within the compose-stack.


## Development

Before you develop with this repo you should install `pre-commit` this will help you fix styling issues before you push your code:

```bash
pip install pre-commit
pre-commit install
```

This installs `pre-commit` as well as installing the packages we use for linting etc.

To work on a specific service or package:
