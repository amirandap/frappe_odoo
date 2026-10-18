<template>
  <div
    v-if="events.length"
    class="rounded-md border border-outline-gray-1 bg-surface-base flex flex-col gap-10"
  >
    <div class="flex items-center gap-2 px-4 pt-4">
      <LucideDatabase class="size-4 text-ink-gray-5" />
      <h3 class="text-lg font-semibold text-ink-gray-8">
        {{ __("Odoo Order Timeline") }}
      </h3>
      <span v-if="orderName" class="text-xs text-ink-gray-5">{{ orderName }}</span>
    </div>
    <div class="relative mx-4">
      <div
        v-show="showLeftFade"
        class="pointer-events-none absolute inset-y-0 left-0 z-10 w-10 bg-gradient-to-r from-[var(--surface-base)] to-transparent"
      />
      <div
        v-show="showRightFade"
        class="pointer-events-none absolute inset-y-0 right-0 z-10 w-10 bg-gradient-to-l from-[var(--surface-base)] to-transparent"
      />
      <div
        ref="scroller"
        class="overflow-x-auto hide-scrollbar"
        @scroll.passive="updateScrollFades"
      >
        <div class="flex w-max min-w-full items-start pl-8 pr-16 pb-16 pt-8">
          <template v-for="(event, index) in events" :key="index">
            <span
              v-if="index > 0"
              class="relative mt-[3px] h-0.5 flex-none rounded-full bg-[var(--outline-gray-2)]"
              :style="{ width: `${legWidth(index)}px` }"
            />
            <Tooltip :hover-delay="0.2" arrow-class="!hidden">
              <span
                class="group relative flex-none size-2.5 rounded-full"
                :class="toneClass(event.tone)"
              >
                <span
                  class="absolute left-1/2 top-4 -translate-x-1/2 whitespace-nowrap text-center"
                >
                  <b class="block text-sm text-ink-gray-8">{{ event.title }}</b>
                  <span class="block text-xs text-ink-gray-5">
                    {{ formatDateTime(event.at) }}
                  </span>
                </span>
              </span>
              <template #body>
                <div
                  class="max-w-xs space-y-1 rounded-md border border-outline-gray-1 bg-surface-elevation-2 px-3 py-2 shadow-sm"
                >
                  <span class="block text-xs text-ink-gray-8">
                    {{ event.subtitle }}
                  </span>
                  <span class="block text-xs text-ink-gray-5">
                    {{ formatDateTime(event.at) }}
                  </span>
                </div>
              </template>
            </Tooltip>
          </template>
        </div>
      </div>
    </div>
    <div
      class="flex flex-wrap gap-x-4 gap-y-1 px-4 pb-4 text-xs text-ink-gray-5"
    >
      <span
        v-for="item in LEGEND"
        :key="item.label"
        class="flex items-center gap-1.5"
      >
        <span class="size-2 rounded-full" :class="item.colorClass" />
        {{ item.label }}
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { __ } from "@/translation";
import { dayjsLocal, Tooltip } from "frappe-ui";
import { computed, ref } from "vue";
import LucideDatabase from "~icons/lucide/database";

export interface OdooTimelineEvent {
  at: string;
  kind: "created" | "pipeline" | "field_change" | "note" | string;
  title: string;
  subtitle?: string;
  tone?: "gray" | "blue" | "green" | "amber" | "red";
}

const props = defineProps<{
  events: OdooTimelineEvent[];
  orderName?: string;
}>();

const events = computed(() => props.events ?? []);

const TONE_CLASS: Record<string, string> = {
  gray: "bg-[var(--outline-gray-4)]",
  blue: "bg-[var(--ink-blue-6)]",
  green: "bg-[var(--ink-green-6)]",
  amber: "bg-[var(--ink-amber-6)]",
  red: "bg-[var(--ink-red-6)]",
};

function toneClass(tone?: string): string {
  return TONE_CLASS[tone ?? "gray"] ?? TONE_CLASS.gray;
}

// rough text metrics (~6.5px/char at text-sm) so a leg is always wide enough
// for the two labels it separates not to collide under their dots
function labelHalfWidth(event: OdooTimelineEvent): number {
  const title = (event.title?.length ?? 0) * 6.5;
  const subtitle = (formatDateTime(event.at)?.length ?? 0) * 5.5;
  return Math.max(title, subtitle) / 2;
}

function legWidth(index: number): number {
  const before = events.value[index - 1];
  const after = events.value[index];
  const needed =
    labelHalfWidth(before) + labelHalfWidth(after) + 24;
  return Math.max(48, needed);
}

const LEGEND = [
  { colorClass: TONE_CLASS.gray, label: __("Creación / nota") },
  { colorClass: TONE_CLASS.blue, label: __("Ingesta / pipeline") },
  { colorClass: TONE_CLASS.green, label: __("Campo resuelto") },
  { colorClass: TONE_CLASS.amber, label: __("Totales recalculados") },
];

const scroller = ref<HTMLElement>();
const showLeftFade = ref(false);
const showRightFade = ref(false);

function updateScrollFades(): void {
  const element = scroller.value;
  if (!element) return;
  const overflow = element.scrollWidth - element.clientWidth;
  showLeftFade.value = overflow > 12 && element.scrollLeft > 4;
  showRightFade.value = overflow > 12 && element.scrollLeft < overflow - 4;
}

function formatDateTime(timestamp: string): string {
  const at = dayjsLocal(timestamp);
  return at.year() === dayjsLocal().year()
    ? at.format("MMM D, h:mm a")
    : at.format("MMM D, YYYY, h:mm a");
}
</script>
