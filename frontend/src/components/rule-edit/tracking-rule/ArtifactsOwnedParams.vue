<!--
SPDX-FileCopyrightText: Contributors to the Fedora Project

SPDX-License-Identifier: MIT
-->

<script setup lang="ts">
import UserMultiSelect from "./UserMultiSelect.vue";
</script>

<template>
  <UserMultiSelect
    label="Artifacts owned by:"
    placeholder="Search by FAS Username"
    nooptionstext="No matches on that username found"
    showArtifactsOwnedSummary
  />
</template>
