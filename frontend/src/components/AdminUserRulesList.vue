<!--
SPDX-FileCopyrightText: Contributors to the Fedora Project

SPDX-License-Identifier: MIT
-->

<script setup lang="ts">
import { apiGet, showError } from "@/api";
import type { APIError, Rule } from "@/api/types";
import { CAccordion, CCard, CCardBody } from "@coreui/bootstrap-vue";
import { useQuery } from "vue-query";
import AdminRuleListItem from "./AdminRuleListItem.vue";

const props = defineProps<{
  username: string;
}>();

const url = `/api/v1/admin/rules`;
const {
  isLoading,
  isError,
  data: rules,
  error,
} = useQuery<Rule[], APIError>([url, { username: props.username }], apiGet);
</script>

<template>
  <CCard v-if="isLoading" class="border bg-light py-5">Loading...</CCard>
  <CCard v-else-if="isError" class="border bg-light py-5"
    >Error: {{ showError(error) }}</CCard
  >
  <CCard v-else-if="(rules || []).length === 0" class="border bg-light py-5">
    <CCardBody>
      <h2 class="text-center text-muted">{{ props.username }} has no Rules.</h2>
    </CCardBody>
  </CCard>
  <template v-else>
    <CAccordion>
      <AdminRuleListItem
        v-for="rule in rules"
        :key="JSON.stringify(rule)"
        :rule="rule"
      />
    </CAccordion>
  </template>
</template>

<style src="@vueform/multiselect/themes/default.css"></style>
