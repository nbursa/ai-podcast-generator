import { defineStore } from "pinia";
import type { PodcastItem, PodcastListResponse, PodcastStatus } from "../api";
import { listPodcasts, deletePodcast } from "../api";

export const usePodcastsStore = defineStore("podcasts", {
  state: () => ({
    items: [] as PodcastItem[],
    loading: false as boolean,
    statusFilter: "" as "" | PodcastStatus,
    _timer: null as number | null,
  }),
  actions: {
    async refresh() {
      this.loading = true;
      try {
        const params: any = {};
        if (this.statusFilter) {
          params.status = this.statusFilter;
        }
        const { items }: PodcastListResponse = await listPodcasts(params);
        this.items = items;
      } finally {
        this.loading = false;
      }
      // After refreshing, check if we should stop polling
      if (!this.hasActiveItems() && this._timer) {
        this.stopPolling();
      }
    },
    startPolling(intervalMs = 3000, checkFn?: () => boolean) {
      if (this._timer) return;
      const shouldPoll =
        typeof checkFn === "function" ? checkFn() : this.hasActiveItems();
      if (!shouldPoll) return;
      this._timer = window.setInterval(() => this.refresh(), intervalMs);
    },
    stopPolling() {
      if (this._timer) {
        window.clearInterval(this._timer);
        this._timer = null;
      }
    },
    hasActiveItems() {
      return this.items.some(
        (item) => item.status === "queued" || item.status === "running"
      );
    },
    async remove(id: string) {
      await deletePodcast(id);
      await this.refresh();
    },
    setFilter(status: "" | PodcastStatus) {
      this.statusFilter = status;
      this.refresh();
    },
  },
});
