<!--
SPDX-FileCopyrightText: Contributors to the Fedora Project

SPDX-License-Identifier: MIT
-->

<script setup lang="ts">
import { validationErrorToFormErrors } from "@/api";
import { usePatchRuleMutation } from "@/api/rules";
import type { PostError, Rule } from "@/api/types";
import { useToastStore } from "@/stores/toast";
import { formDataToRuleMutation } from "@/util/forms";
import type { FormKitGroupValue, FormKitNode } from "@formkit/core";
import { FormKit } from "@formkit/vue";
import type { AxiosError } from "axios";
import { useQueryClient } from "vue-query";

const props = defineProps<{
  rule: Rule;
}>();

const toastStore = useToastStore();
const queryClient = useQueryClient();
const { mutateAsync: editMutation } = usePatchRuleMutation();

const handleSubmit = async (
  data: FormKitGroupValue,
  form: FormKitNode | undefined
) => {
  console.log(
    `Will set rule ${data.id}'s' disabled status to ${data.disabled}`
  );
  if (!form) {
    throw Error("No form node?");
  }
  try {
    const response = await editMutation(formDataToRuleMutation(data));
    // Success!
    await queryClient.invalidateQueries([
      "/api/v1/admin/rules",
      {
        username: props.rule.user.name,
      },
    ]);
    toastStore.addToast({
      color: "success",
      title: "Rule enabled",
      content: response.disabled
        ? `Rule "${response.id}" has been successfully disabled.`
        : `Rule "${response.id}" has been successfully enabled.`,
    });
  } catch (err) {
    const error = err as AxiosError<PostError>;
    console.log("Got error response from server:", error);
    if (!error.response) {
      return;
    }
    form.setErrors(validationErrorToFormErrors(error.response.data));
  }
};
</script>

<template>
  <FormKit
    type="form"
    id="rule"
    @submit="handleSubmit"
    :actions="false"
    #default="{ disabled: formDisabled }"
  >
    <FormKit type="hidden" name="id" :value="props.rule.id" />
    <FormKit type="hidden" name="disabled" :value="!props.rule.disabled" />
    <template v-if="props.rule.disabled">
      <FormKit
        @click.stop=""
        type="submit"
        :classes="{ input: 'btn btn-success' }"
        :disabled="formDisabled"
      >
        Enable Rule {{ props.rule.id }}
      </FormKit>
    </template>
    <template v-else>
      <FormKit
        @click.stop=""
        type="submit"
        :classes="{ input: 'btn btn-danger' }"
        :disabled="formDisabled"
      >
        Disable Rule {{ props.rule.id }}
      </FormKit>
    </template>
  </FormKit>
</template>
