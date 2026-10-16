import { Router } from "express";
import { requireAuth, requireRole } from "../auth";

const router = Router();

// Vulnerable: administrative route requiring auth, but missing role check (E1)
router.get("/admin/users", requireAuth, (req, res) => {
  res.json({ users: [{ id: "u-1", name: "Alice" }] });
});

// Safe: administrative route requiring both auth and admin role check
router.delete("/admin/users/:id", requireAuth, requireRole("admin"), (req, res) => {
  res.json({ status: "deleted", id: req.params.id });
});

export default router;
