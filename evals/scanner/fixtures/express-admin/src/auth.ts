import type { Request, Response, NextFunction } from "express";

export interface AuthenticatedUser {
  id: string;
  role: string;
}

export function requireAuth(
  req: Request & { user?: AuthenticatedUser },
  res: Response,
  next: NextFunction
) {
  const token = req.headers.authorization;
  if (!token) {
    return res.status(401).json({ error: "unauthenticated" });
  }
  // Simulated authentication decoding
  req.user = { id: "user-123", role: "member" };
  return next();
}

export function requireRole(role: string) {
  return (req: Request & { user?: AuthenticatedUser }, res: Response, next: NextFunction) => {
    if (!req.user || req.user.role !== role) {
      return res.status(403).json({ error: "forbidden" });
    }
    return next();
  };
}
