<script setup>
import { PROJECT_NAME } from '@/config/project'
defineProps({ compact: Boolean })
</script>

<template>
  <span class="brand">
    <span class="brand-mark">
      <img
        src="/brand/leave-approval.png"
        alt=""
        width="40"
        height="40"
        draggable="false"
      />
    </span>
    <span v-if="!compact">{{ PROJECT_NAME }}</span>
  </span>
</template>
