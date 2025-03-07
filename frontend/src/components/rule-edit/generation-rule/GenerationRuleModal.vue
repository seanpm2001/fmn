<!--
SPDX-FileCopyrightText: Contributors to the Fedora Project

SPDX-License-Identifier: MIT
-->

<script setup lang="ts">
import { SEVERITIES } from "@/api/constants";
import type { GenerationRule } from "@/api/types";
import {
  CModal,
  CModalBody,
  CModalHeader,
  CModalTitle,
} from "@coreui/bootstrap-vue";
import type { FormKitGroupValue, FormKitNode } from "@formkit/core";
import { computed, ref } from "vue";
import DestinationList from "./DestinationList.vue";
import FilterList from "./FilterList.vue";

const props = defineProps<{
  visible: boolean;
  rule?: GenerationRule;
  title: string;
  buttonLabel: string;
}>();
const emit = defineEmits<{
  (e: "submit", rule: GenerationRule): void;
  (e: "close"): void;
}>();

const node = ref<{ node: FormKitNode } | null>(null);

const handleSubmit = async (data: FormKitGroupValue) => {
  emit("submit", data as GenerationRule);
};
const handleClose = async () => {
  emit("close");
};

const defaultValue = computed(
  () =>
    props.rule || {
      filters: { severities: SEVERITIES.slice(1).map((s) => s.label) },
    }
);
</script>

<template>
  <CModal
    size="lg"
    scrollable
    :visible="props.visible"
    @close="handleClose"
    alignment="center"
  >
    <!-- Catch and prevent the click event on the close button so that it does not submit the form -->
    <CModalHeader @click.prevent="">
      <CModalTitle>{{ props.title }}</CModalTitle>
    </CModalHeader>
    <CModalBody>
      <FormKit
        type="form"
        ref="node"
        @submit="handleSubmit"
        :actions="false"
        :value="defaultValue"
      >
        <DestinationList />
        <FilterList />
        <div class="text-center my-4">
          <FormKit type="submit" :class="['btn', 'btn-primary']">{{
            props.buttonLabel
          }}</FormKit>
        </div>
      </FormKit>
    </CModalBody>
  </CModal>
</template>
