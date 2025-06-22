# AIGENT - A Local AI Agent Framework 🚀

AIGENT is a flexible, self-hosted framework for creating and interacting with multiple, persona-driven AI agents (Aigents) powered by local Large Language Models (LLMs) via Ollama. It provides a full-stack solution with a Django backend, a vanilla JavaScript frontend, and asynchronous task processing for a responsive user experience.

The core idea is to enable different "Aigents" with unique personalities, instructions, and output formats (like Markdown or interactive HTML widgets) to coexist within the same application, allowing the user to switch between them on the fly.

## ✨ Core Features

*   **Multi-Agent Architecture**: Define and run multiple Aigents, each with a distinct persona, system prompt, and capabilities.
*   **Dynamic Output Formatting**: Aigents can respond in different formats, including:
    *   **Markdown**: For standard text-based conversations.
    *   **Rendered HTML**: For generating interactive widgets and rich content directly in the chat.
*   **Stateful Conversations**: Both the Aigent and the User have persistent JSON state fields that the LLM can modify, allowing for memory, context, and task tracking across sessions.
*   **Local First with Ollama**: Designed to connect to a local Ollama instance, ensuring privacy and offline capability.
*   **Asynchronous Task Processing**: User messages are handled by Celery workers to prevent HTTP timeouts during long-running LLM inferences.
*   **User Authentication**: Standard Django-based user login and password management.
*   **Easy Customization**: New Aigents and their prompt templates can be added by simply editing a JSON fixture file.
*   **Modern UI**: A clean, themeable chat interface (Light, Dark, Memphis) with a settings menu for switching Aigents and managing history.
*   **Admin Interface**: A full Django admin panel for managing users, Aigents, prompts, and chat history with pretty-printed JSON for easy debugging.

## 🛠️ Technology Stack

*   **Backend**: Django, Django REST Framework, PostgreSQL
*   **Frontend**: HTML5, CSS3, Vanilla JavaScript (no frameworks)
*   **LLM Integration**: Ollama
*   **Async Task Queue**: Celery, RabbitMQ (as a message broker), Redis (as a result backend)
*   **Infrastructure**: Docker, Docker Compose
*   **WSGI Server**: Gunicorn (for production)

## 📁 Project Structure

```
AIGENT/
├── backend/
│   ├── aigents/         # Core app: Models (Aigent, Prompt), Views, Tasks
│   │   ├── management/  # Custom Django commands (e.g., seed_initial_data)
│   │   └── tasks.py     # Celery tasks for processing LLM requests
│   ├── fixtures/
│   │   └── initial_data.json # Seed data for creating default Aigents
│   ├── lba_project/     # Django project settings, Celery config, main URLs
│   ├── static/          # Frontend CSS and JavaScript
│   ├── templates/       # HTML templates for the UI
│   └── users/           # Custom User model and authentication views
├── .env.example         # Example environment variables
├── docker-compose.yml   # Defines all services (db, backend, celery, etc.)
└── README.md            # This file
```

## ⚙️ Setup and Installation

### Prerequisites

1.  **Docker & Docker Compose**: Ensure you have them installed on your system.
2.  **Ollama**: You must have a running Ollama instance. [Install it from the official website](https://ollama.com/).
3.  **Pull an LLM Model**: Pull the model you intend to use. The default Aigents use `phi4`.
    ```bash
    ollama pull phi4
    ```

### Step-by-Step Installation

1.  **Clone the Repository**
    ```bash
    git clone https://github.com/VOVSn/AIGENT
    cd AIGENT
    ```

2.  **Configure Environment Variables**
    Copy the example `.env` file and customize it.
    ```bash
    cp .env.example .env
    ```
    Now, open the `.env` file and fill in the values. Pay close attention to these:

    *   `DJANGO_SECRET_KEY`: Generate a new secret key. You can use an online generator or Python `os.urandom(24).hex()`.
    *   `POSTGRES_...`, `RABBITMQ_...`, `REDIS_...`: You can leave the default passwords for local development or set your own.
    *   `OLLAMA_DEFAULT_ENDPOINT`: This is critical.
        *   On **macOS and Windows** with Docker Desktop, `http://host.docker.internal:11434` should work out-of-the-box.
        *   On **Linux**, you may need to find your host IP address on the Docker bridge network (e.g., `ip addr show docker0`) and use that IP, or use `extra_hosts` in `docker-compose.yml`.

3.  **Build and Run the Services**
    From the root `AIGENT/` directory, run:
    ```bash
    docker-compose up --build -d
    ```
    This command will build the Docker images, start all services in detached mode, apply database migrations, and seed the initial Aigent data.

4.  **Create a Superuser Account**
    To log in for the first time, you need to create a user account.
    ```bash
    docker-compose exec backend python manage.py createsuperuser
    ```
    Follow the prompts to create your username and password.

## 🚀 Usage

Once all the services are running, you can access the different parts of the application:

*   **Main Chat Application**: [http://localhost:8000/chat/](http://localhost:8000/chat/)
    *   Log in with the superuser credentials you just created.
*   **Django Admin Panel**: [http://localhost:8000/admin/](http://localhost:8000/admin/)
    *   Manage users, Aigents, and view chat history. The JSON state fields are pretty-printed for readability.
*   **Celery Monitoring (Flower)**: [http://localhost:5555/](http://localhost:5555/)
    *   Monitor the status of Celery workers and tasks. Login with the RabbitMQ credentials from your `.env` file (default: `guest`/`guest`).

## 🎨 Customizing and Adding New Aigents

Adding a new Aigent is simple and doesn't require changing any Python code.

1.  **Open the Fixture File**: Edit `backend/fixtures/initial_data.json`.
2.  **Define a New Prompt (Optional)**: If your new Aigent needs a unique prompt structure, add it to the `prompts` list. Give it a unique `name`.
    ```json
    {
      "name": "MyNewPrompt_v1",
      "template_str": "Your custom prompt template here... using {placeholders}."
    }
    ```
3.  **Define the New Aigent**: Add a new object to the `aigents` list.
    *   Set a unique `name`.
    *   `is_active` should be `false` unless you want it to be the default.
    *   `presentation_format`: Choose `markdown` or `html`.
    *   `system_persona_prompt`: This is where you define the Aigent's personality and core instructions.
    *   `ollama_model_name`: Specify the Ollama model it should use.
    *   `aigent_state`: Define its initial internal state.
    *   `default_prompt_template_name`: Link it to the `name` of the prompt you want it to use.

4.  **Re-seed the Database**: Restart your containers to apply the changes. The `seed_initial_data` command in `docker-compose.yml` will run on startup. For a running system, you could run it manually:
    ```bash
    docker-compose exec backend python manage.py seed_initial_data --overwrite
    ```
    The `--overwrite` flag will update existing Aigents and Prompts with the same name.

Your new Aigent will now appear in the "Active Aigent" dropdown in the chat settings menu!

## 📄 License

This project is licensed under the MIT License. See the LICENSE file for details.
