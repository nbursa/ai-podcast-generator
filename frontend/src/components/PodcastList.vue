<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch, defineExpose } from "vue";
import { usePodcastsStore } from "../stores/podcasts";
import type { PodcastStatus } from "../api";

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || "http://localhost:3000";

const store = usePodcastsStore();
const status = ref<"" | PodcastStatus>("");

function nice(ts: string) {
  try {
    return new Date(ts).toLocaleString();
  } catch {
    return ts;
  }
}

async function refresh() {
  await store.refresh();
  store.startPolling(3000);
}

async function remove(id: string) {
  await store.remove(id);
}

onMounted(async () => {
  await store.refresh();
  store.startPolling(3000);
});
onUnmounted(() => {
  store.stopPolling();
});

watch(status, (val) => {
  store.setFilter(val);
});

// expose to parent
defineExpose({ refresh });
</script>

<template>
  <section class="rounded border border-zinc-300 p-4 space-y-3">
    <header class="flex items-center justify-between">
      <h2 class="text-lg font-medium">Episodes</h2>
      <div class="flex items-center gap-2">
        <select v-model="status" class="input text-sm">
          <option value="">all</option>
          <option value="queued">queued</option>
          <option value="running">running</option>
          <option value="done">done</option>
          <option value="failed">failed</option>
          <option value="cancelled">cancelled</option>
        </select>
        <button
          @click="refresh"
          :disabled="store.loading"
          class="btn-secondary"
        >
          Refresh
        </button>
      </div>
    </header>

    <ul class="grid gap-3">
      <li
        v-for="item in store.items"
        :key="item.id"
        class="p-3 rounded border border-zinc-200"
      >
        <div class="flex flex-col gap-1">
          <div class="flex items-baseline gap-2">
            <span class="font-semibold">{{ item.title }}</span>
            <span v-if="item.status !== 'done'" class="text-sm text-zinc-600">
              · {{ item.status }} ·
              <span class="animate-pulse">processing</span>
            </span>
            <span v-else class="text-sm text-zinc-600">· done</span>
          </div>
          <p v-if="item.description" class="text-sm">{{ item.description }}</p>
          <div class="text-xs text-zinc-600 flex gap-3">
            <span>created: {{ nice(item.created_at) }}</span>
            <span>updated: {{ nice(item.updated_at) }}</span>
          </div>
          <p v-if="item.error" class="text-red-700 text-sm">
            Error: {{ item.error }}
          </p>
        </div>

        <div class="mt-2 flex items-center gap-3">
          <audio
            v-if="item.audio_url"
            :src="
              item.audio_url.startsWith('http')
                ? item.audio_url
                : apiBaseUrl + item.audio_url
            "
            controls
            preload="none"
            class="w-full"
          ></audio>
          <button class="btn-danger" @click="remove(item.id)">Delete</button>
        </div>
      </li>
    </ul>

    <p
      v-if="!store.items.length && !store.loading"
      class="text-sm text-zinc-600"
    >
      No episodes yet.
    </p>
  </section>
</template>
