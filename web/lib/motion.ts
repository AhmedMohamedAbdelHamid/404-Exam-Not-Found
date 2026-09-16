export const motionTokens = {
  micro: 0.16,
  card: 0.24,
  page: 0.38,
  ease: [0.22, 1, 0.36, 1] as const,
  spring: { type: "spring" as const, stiffness: 380, damping: 32 },
};

export const cardEntrance = {
  hidden: { opacity: 0, y: 12 },
  visible: { opacity: 1, y: 0 },
};
