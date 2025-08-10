<template>
  <main class="max-w-4xl mx-auto p-6 space-y-6">
    <h1 class="text-2xl font-semibold">AI Podcast Generator</h1>
    <PodcastForm @created="onCreated" />
    <PodcastList ref="listRef" />
  </main>
</template>

<script setup lang="ts">
import { ref } from "vue";
import PodcastForm from "./components/PodcastForm.vue";
import PodcastList from "./components/PodcastList.vue";

const listRef = ref<InstanceType<typeof PodcastList> | null>(null);
function onCreated() {
  listRef.value?.refresh();
}
</script>
