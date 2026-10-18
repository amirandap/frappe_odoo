<template>
  <div class="flex items-center gap-3">
    <Avatar
      :label="displayName"
      :image="contactImage"
      size="3xl"
    />
    <div class="flex min-w-0 flex-1 flex-col gap-1.5">
      <Tooltip :text="displayName">
        <div class="flex min-w-0 items-center gap-1.5 w-fit max-w-[65%]">
          <p
            class="min-h-[1lh] cursor-pointer truncate text-lg font-medium text-ink-gray-7 hover:text-ink-gray-9"
            @click="openContact(contact.data?.name)"
          >
            {{ displayName }}
          </p>
        </div>
      </Tooltip>
      <p
        v-if="contact.data?.company_name"
        class="truncate text-p-sm text-ink-gray-6"
      >
        {{ contact.data.company_name }}
      </p>
      <div class="flex items-center gap-1 text-p-sm text-ink-gray-6">
        <p
          class="cursor-copy transition-colors hover:text-ink-gray-8"
          @click="
            copyToClipboard(
              ticket.doc.name,
              `Ticket #${ticket.doc.name} copied`
            )
          "
        >
          #{{ ticket.doc.name }}
        </p>
        <div class="flex items-center">
          <span>{{
            ticket.doc.via_customer_portal ? __("via Portal") : __("via Email")
          }}</span>
        </div>
      </div>
    </div>
    <Tooltip v-if="isCallingEnabled" :text="__('Call contact')">
      <Button variant="ghost" @click="callContact">
        <template #icon>
          <PhoneIcon class="size-4" />
        </template>
      </Button>
    </Tooltip>
    <SetContactPhoneModal
      v-model="showPhoneModal"
      :name="contact.data?.name ?? ''"
      @onUpdate="contact.reload"
    />
  </div>
</template>

<script setup lang="ts">
import { useShortcut } from "@/composables/shortcuts";
import { useTelephonyStore } from "@/stores/telephony";
import { useUserStore } from "@/stores/user";
import { TicketContactSymbol, TicketSymbol } from "@/types";
import { copyToClipboard, openContact } from "@/utils";
import { Avatar, Button, Tooltip } from "frappe-ui";
import { storeToRefs } from "pinia";
import { computed, inject, ref } from "vue";
import PhoneIcon from "../icons/PhoneIcon.vue";
import SetContactPhoneModal from "../ticket/SetContactPhoneModal.vue";

const telephonyStore = useTelephonyStore();
const { getUser } = useUserStore();
const { isCallingEnabled } = storeToRefs(telephonyStore);
const showPhoneModal = ref(false);

const ticket = inject(TicketSymbol)!;

const contact = inject(TicketContactSymbol)!;
const displayName = computed(
  () =>
    contact.value?.data?.full_name?.trim() ||
    contact.value?.data?.name ||
    contact.value?.data?.email_id ||
    ""
);
const contactImage = computed(() => {
  if (!contact.value?.data) return "";
  const email = contact.value?.data?.email_id ?? "";
  return (
    contact.value?.data?.image || (email && getUser(email)?.user_image) || ""
  );
});

const callContact = () => {
  if (!contact.value.data.mobile_no && !contact.value.data.phone) {
    showPhoneModal.value = true;
    return;
  }
  telephonyStore.makeCall({
    number: contact.value.data.mobile_no || contact.value.data.phone,
    doctype: "HD Ticket",
    docname: ticket.value.name,
  });
};

useShortcut({ meta: true, shift: true, key: "." }, () => {
  copyToClipboard(window.location.href, `Ticket URL copied`);
});

useShortcut({ meta: true, key: "." }, () => {
  copyToClipboard(
    ticket.value.doc.name,
    `Ticket #${ticket.value.doc.name} copied`
  );
});
</script>
