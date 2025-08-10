<script setup lang="ts">
import { ref } from "vue";
import type { PodcastCreatePayload } from "../api";
import { createPodcast } from "../api";

const title = ref("");
const description = ref<string | null>("");
const voice = ref<string | null>("en");
const materialsSet = ref<"1" | "2">("1");

const loading = ref(false);
const error = ref("");
const createdId = ref("");

const emit = defineEmits<{ (e: "created", id: string): void }>();

async function submit() {
  error.value = "";
  createdId.value = "";
  loading.value = true;
  try {
    const payload: PodcastCreatePayload = {
      title: title.value.trim(),
      description: description.value?.trim() || null,
      voice: voice.value?.trim() || null,
      materials_set: materialsSet.value,
    };
    const { id } = await createPodcast(payload);
    createdId.value = id;
    emit("created", id);
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e?.message || "Failed to create";
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <form
    @submit.prevent="submit"
    class="rounded border border-zinc-300 p-4 space-y-4"
  >
    <h2 class="text-lg font-medium">Create podcast</h2>

    <div class="grid gap-2">
      <label class="text-sm">Title</label>
      <input
        v-model="title"
        required
        class="input"
        placeholder="Episode title"
      />
    </div>

    <div class="grid gap-2">
      <label class="text-sm">Description</label>
      <textarea
        v-model="description"
        class="input min-h-[96px]"
        placeholder="Optional"
      ></textarea>
    </div>

    <div class="grid gap-2">
      <label class="text-sm">Voice</label>
      <input v-model="voice" class="input" placeholder="en" />
    </div>

    <div class="grid gap-2">
      <label class="text-sm">Materials set</label>
      <select v-model="materialsSet" class="input">
        <option value="1">1</option>
        <option value="2">2</option>
      </select>
    </div>

    <div class="flex items-center gap-3">
      <button :disabled="loading" class="btn-primary">
        <span v-if="!loading">Create</span>
        <span v-else>Creating…</span>
      </button>
      <p v-if="createdId" class="text-green-700">
        Created:
        <code class="bg-zinc-200 px-1 rounded">{{ createdId }}</code>
      </p>
    </div>

    <p v-if="error" class="text-red-700">{{ error }}</p>
  </form>
</template>
