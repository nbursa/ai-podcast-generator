# AI Podcast Generator Frontend

## Project Overview

This is the frontend application for the AI Podcast Generator project. It is built using Vue 3 with TypeScript, Pinia for state management, and TailwindCSS for styling. The frontend communicates with a FastAPI backend to manage podcast creation, listing, and playback.

## Features

- **Create Podcast Form:** Easily create new podcast episodes with a simple form.
- **Podcast List:** View a list of podcasts with an integrated audio player for each episode.
- **Filtering:** Filter podcasts by their status (e.g., active, completed).
- **Delete Functionality:** Remove unwanted podcast episodes from the list.
- **Automatic Polling:** While active podcast episodes exist, the app automatically polls the backend to update the status.
- **Form Reset:** The create podcast form automatically resets after a podcast is successfully created.

## Tech Stack

- Vue 3
- Vite
- TypeScript
- Pinia
- TailwindCSS
- Axios

## Project Setup

1. Install dependencies:

```bash
pnpm install
# or
npm install
```

2. Run the development server:

```bash
pnpm dev
# or
npm run dev
```

3. Build for production:

```bash
pnpm build
# or
npm run build
```

## Configuration

The application expects a `VITE_API_BASE` environment variable that defines the base URL of the backend API. This should be set in your `.env` file or environment before running the app.

Example `.env` file:

```
VITE_API_BASE=http://localhost:8000/api
```

## Folder Structure

- `src/components`: Contains Vue components used throughout the application.
- `src/stores`: Pinia stores for state management.
- `src/api.ts`: Axios instance and API-related functions for communicating with the backend.

## Future Improvements

- Custom audio player UI with enhanced controls.
- Progress bar for podcast playback.
- Improved error handling and user notifications.
- Mobile responsiveness and optimizations for smaller screens.
