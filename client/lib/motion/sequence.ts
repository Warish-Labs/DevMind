/**
 * Animation Sequence Helper
 * Provides clean timer orchestration with immediate bypass under reduced motion.
 */

export interface SequenceStep {
  delayMs: number;
  run: () => void;
}

export class SequenceRunner {
  private timers: NodeJS.Timeout[] = [];
  private isRunning: boolean = false;

  run(steps: SequenceStep[], reducedMotion: boolean = false) {
    this.cancel();

    if (reducedMotion) {
      // Execute all step callbacks immediately
      steps.forEach((s) => s.run());
      return;
    }

    this.isRunning = true;
    steps.forEach((step) => {
      const timer = setTimeout(() => {
        step.run();
      }, step.delayMs);
      this.timers.push(timer);
    });
  }

  cancel() {
    this.timers.forEach(clearTimeout);
    this.timers = [];
    this.isRunning = false;
  }

  get active(): boolean {
    return this.isRunning;
  }
}
