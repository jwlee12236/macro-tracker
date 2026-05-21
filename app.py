"""
Macro Tracker — FastAPI + SQLite
Run:  python app.py
Open: http://localhost:8001
"""

import sqlite3
import json
import os
import math
from datetime import date, datetime, timedelta
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

# ── Config ────────────────────────────────────────────────────────────────────

DB_PATH = Path(__file__).parent / "macro.db"
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

app = FastAPI(title="Macro Tracker", docs_url="/api/docs")

# ── Database ──────────────────────────────────────────────────────────────────

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

@contextmanager
def db():
    conn = get_conn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db():
    with db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS ingredients (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                name         TEXT NOT NULL,
                brand        TEXT DEFAULT '',
                category     TEXT DEFAULT 'other',
                serving_size REAL NOT NULL DEFAULT 100,
                serving_unit TEXT NOT NULL DEFAULT 'g',
                calories     REAL NOT NULL DEFAULT 0,
                protein      REAL NOT NULL DEFAULT 0,
                carbs        REAL NOT NULL DEFAULT 0,
                fat          REAL NOT NULL DEFAULT 0,
                fiber        REAL DEFAULT 0,
                sugar        REAL DEFAULT 0,
                sodium       REAL DEFAULT 0,
                notes        TEXT DEFAULT '',
                is_active    INTEGER DEFAULT 1,
                created_at   TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS recipes (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                name           TEXT NOT NULL,
                description    TEXT DEFAULT '',
                category       TEXT DEFAULT 'meal',
                total_servings REAL NOT NULL DEFAULT 1,
                notes          TEXT DEFAULT '',
                is_active      INTEGER DEFAULT 1,
                created_at     TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS recipe_components (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                recipe_id     INTEGER NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
                ingredient_id INTEGER NOT NULL REFERENCES ingredients(id),
                quantity      REAL NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS food_log (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                date       TEXT NOT NULL,
                meal_type  TEXT NOT NULL DEFAULT 'snack',
                food_type  TEXT NOT NULL,
                food_id    INTEGER NOT NULL,
                food_name  TEXT NOT NULL,
                servings   REAL NOT NULL DEFAULT 1,
                calories   REAL NOT NULL DEFAULT 0,
                protein    REAL NOT NULL DEFAULT 0,
                carbs      REAL NOT NULL DEFAULT 0,
                fat        REAL NOT NULL DEFAULT 0,
                fiber      REAL DEFAULT 0,
                notes      TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS body_config (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                key         TEXT UNIQUE NOT NULL,
                label       TEXT NOT NULL,
                unit        TEXT NOT NULL DEFAULT '',
                category    TEXT DEFAULT 'measurement',
                target_value REAL DEFAULT NULL,
                is_active   INTEGER DEFAULT 1,
                position    INTEGER DEFAULT 0,
                created_at  TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS body_measurements (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                date            TEXT NOT NULL,
                measurable_key  TEXT NOT NULL,
                value           REAL NOT NULL,
                created_at      TEXT DEFAULT (datetime('now')),
                UNIQUE(date, measurable_key)
            );

            CREATE TABLE IF NOT EXISTS macro_targets (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                calories   REAL DEFAULT NULL,
                protein    REAL DEFAULT NULL,
                carbs      REAL DEFAULT NULL,
                fat        REAL DEFAULT NULL,
                fiber      REAL DEFAULT NULL,
                updated_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS workouts (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                date             TEXT NOT NULL,
                name             TEXT NOT NULL,
                workout_type     TEXT DEFAULT 'other',
                duration_minutes INTEGER DEFAULT NULL,
                calories_burned  REAL DEFAULT NULL,
                notes            TEXT DEFAULT '',
                created_at       TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS workout_exercises (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                workout_id       INTEGER NOT NULL REFERENCES workouts(id) ON DELETE CASCADE,
                exercise_name    TEXT NOT NULL,
                sets             INTEGER DEFAULT NULL,
                reps             INTEGER DEFAULT NULL,
                weight           REAL DEFAULT NULL,
                weight_unit      TEXT DEFAULT 'kg',
                duration_seconds INTEGER DEFAULT NULL,
                distance         REAL DEFAULT NULL,
                distance_unit    TEXT DEFAULT 'km',
                notes            TEXT DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS ai_insights (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                week_start TEXT NOT NULL,
                content    TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now'))
            );
        """)

        # Seed default body config
        existing = conn.execute("SELECT COUNT(*) FROM body_config").fetchone()[0]
        if existing == 0:
            defaults = [
                ("weight",       "Weight",       "lbs", "weight",      0),
                ("height",       "Height",       "in",  "weight",      1),
                ("body_fat_pct", "Body Fat",     "%",   "composition", 2),
                ("muscle_mass",  "Muscle Mass",  "lbs", "composition", 3),
                ("neck",         "Neck",         "in",  "measurement", 4),
                ("waist",        "Waist",        "in",  "measurement", 5),
                ("hips",         "Hips",         "in",  "measurement", 6),
                ("chest",        "Chest",        "in",  "measurement", 7),
                ("left_arm",     "Left Arm",     "in",  "measurement", 8),
                ("right_arm",    "Right Arm",    "in",  "measurement", 9),
                ("left_thigh",   "Left Thigh",   "in",  "measurement", 10),
                ("right_thigh",  "Right Thigh",  "in",  "measurement", 11),
            ]
            conn.executemany(
                "INSERT INTO body_config (key,label,unit,category,position) VALUES (?,?,?,?,?)",
                defaults
            )

# ── Helpers ───────────────────────────────────────────────────────────────────

def row_to_dict(row):
    return dict(row) if row else None

def calc_recipe_macros(conn, recipe_id: int) -> dict:
    """Sum ingredient macros for a recipe (scaled by component quantity = # of servings)."""
    comps = conn.execute("""
        SELECT rc.quantity, i.calories, i.protein, i.carbs, i.fat, i.fiber
        FROM recipe_components rc
        JOIN ingredients i ON i.id = rc.ingredient_id
        WHERE rc.recipe_id = ?
    """, (recipe_id,)).fetchall()

    totals = dict(calories=0.0, protein=0.0, carbs=0.0, fat=0.0, fiber=0.0)
    for c in comps:
        q = c["quantity"]
        totals["calories"] += (c["calories"] or 0) * q
        totals["protein"]  += (c["protein"]  or 0) * q
        totals["carbs"]    += (c["carbs"]    or 0) * q
        totals["fat"]      += (c["fat"]      or 0) * q
        totals["fiber"]    += (c["fiber"]    or 0) * q
    return {k: round(v, 2) for k, v in totals.items()}

def macros_per_serving_for_recipe(conn, recipe_id: int) -> dict:
    """Macros per 1 serving of a recipe."""
    recipe = conn.execute("SELECT total_servings FROM recipes WHERE id=?", (recipe_id,)).fetchone()
    if not recipe:
        return {}
    total = calc_recipe_macros(conn, recipe_id)
    s = recipe["total_servings"] or 1
    return {k: round(v / s, 2) for k, v in total.items()}

# ── Pydantic Models ───────────────────────────────────────────────────────────

class IngredientIn(BaseModel):
    name: str
    brand: str = ""
    category: str = "other"
    serving_size: float = 100
    serving_unit: str = "g"
    calories: float = 0
    protein: float = 0
    carbs: float = 0
    fat: float = 0
    fiber: float = 0
    sugar: float = 0
    sodium: float = 0
    notes: str = ""

class RecipeIn(BaseModel):
    name: str
    description: str = ""
    category: str = "meal"
    total_servings: float = 1
    notes: str = ""

class RecipeComponentIn(BaseModel):
    ingredient_id: int
    quantity: float = 1

class FoodLogIn(BaseModel):
    date: str
    meal_type: str = "snack"
    food_type: str  # 'ingredient' or 'recipe'
    food_id: int
    servings: float = 1
    notes: str = ""

class BodyConfigIn(BaseModel):
    key: str
    label: str
    unit: str = ""
    category: str = "measurement"
    target_value: Optional[float] = None

class BodyMeasurementIn(BaseModel):
    date: str
    measurable_key: str
    value: float

class MacroTargetsIn(BaseModel):
    calories: Optional[float] = None
    protein: Optional[float] = None
    carbs: Optional[float] = None
    fat: Optional[float] = None
    fiber: Optional[float] = None

class WorkoutIn(BaseModel):
    date: str
    name: str
    workout_type: str = "other"
    duration_minutes: Optional[int] = None
    calories_burned: Optional[float] = None
    notes: str = ""

class ExerciseIn(BaseModel):
    exercise_name: str
    sets: Optional[int] = None
    reps: Optional[int] = None
    weight: Optional[float] = None
    weight_unit: str = "kg"
    duration_seconds: Optional[int] = None
    distance: Optional[float] = None
    distance_unit: str = "km"
    notes: str = ""

class BodyConfigUpdateIn(BaseModel):
    label: Optional[str] = None
    unit: Optional[str] = None
    target_value: Optional[float] = None
    is_active: Optional[int] = None

# ── API: Ingredients ──────────────────────────────────────────────────────────

@app.get("/api/ingredients")
def list_ingredients(q: str = Query(""), category: str = Query("")):
    with db() as conn:
        sql = "SELECT * FROM ingredients WHERE is_active=1"
        params = []
        if q:
            sql += " AND (name LIKE ? OR brand LIKE ?)"
            params += [f"%{q}%", f"%{q}%"]
        if category:
            sql += " AND category=?"
            params.append(category)
        sql += " ORDER BY name"
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

@app.post("/api/ingredients", status_code=201)
def create_ingredient(ing: IngredientIn):
    with db() as conn:
        cur = conn.execute("""
            INSERT INTO ingredients
              (name,brand,category,serving_size,serving_unit,calories,protein,carbs,fat,fiber,sugar,sodium,notes)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (ing.name, ing.brand, ing.category, ing.serving_size, ing.serving_unit,
              ing.calories, ing.protein, ing.carbs, ing.fat, ing.fiber, ing.sugar,
              ing.sodium, ing.notes))
        return {"id": cur.lastrowid, "name": ing.name}

@app.put("/api/ingredients/{ing_id}")
def update_ingredient(ing_id: int, ing: IngredientIn):
    with db() as conn:
        conn.execute("""
            UPDATE ingredients SET
              name=?,brand=?,category=?,serving_size=?,serving_unit=?,
              calories=?,protein=?,carbs=?,fat=?,fiber=?,sugar=?,sodium=?,notes=?
            WHERE id=?
        """, (ing.name, ing.brand, ing.category, ing.serving_size, ing.serving_unit,
              ing.calories, ing.protein, ing.carbs, ing.fat, ing.fiber, ing.sugar,
              ing.sodium, ing.notes, ing_id))
        return {"status": "updated"}

@app.delete("/api/ingredients/{ing_id}")
def delete_ingredient(ing_id: int):
    with db() as conn:
        conn.execute("UPDATE ingredients SET is_active=0 WHERE id=?", (ing_id,))
        return {"status": "deleted"}

# ── API: Recipes ──────────────────────────────────────────────────────────────

@app.get("/api/recipes")
def list_recipes(q: str = Query("")):
    with db() as conn:
        sql = "SELECT * FROM recipes WHERE is_active=1"
        params = []
        if q:
            sql += " AND name LIKE ?"
            params.append(f"%{q}%")
        sql += " ORDER BY name"
        rows = conn.execute(sql, params).fetchall()
        result = []
        for row in rows:
            r = dict(row)
            r["macros_per_serving"] = macros_per_serving_for_recipe(conn, r["id"])
            result.append(r)
        return result

@app.get("/api/recipes/{recipe_id}")
def get_recipe(recipe_id: int):
    with db() as conn:
        row = conn.execute("SELECT * FROM recipes WHERE id=?", (recipe_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Recipe not found")
        r = dict(row)
        # Components with ingredient details
        comps = conn.execute("""
            SELECT rc.id, rc.quantity, i.id as ingredient_id, i.name, i.brand,
                   i.serving_size, i.serving_unit, i.calories, i.protein, i.carbs,
                   i.fat, i.fiber
            FROM recipe_components rc
            JOIN ingredients i ON i.id = rc.ingredient_id
            WHERE rc.recipe_id = ?
        """, (recipe_id,)).fetchall()
        r["components"] = [dict(c) for c in comps]
        r["macros_per_serving"] = macros_per_serving_for_recipe(conn, recipe_id)
        r["total_macros"] = calc_recipe_macros(conn, recipe_id)
        return r

@app.post("/api/recipes", status_code=201)
def create_recipe(rec: RecipeIn):
    with db() as conn:
        cur = conn.execute("""
            INSERT INTO recipes (name,description,category,total_servings,notes)
            VALUES (?,?,?,?,?)
        """, (rec.name, rec.description, rec.category, rec.total_servings, rec.notes))
        return {"id": cur.lastrowid, "name": rec.name}

@app.put("/api/recipes/{recipe_id}")
def update_recipe(recipe_id: int, rec: RecipeIn):
    with db() as conn:
        conn.execute("""
            UPDATE recipes SET name=?,description=?,category=?,total_servings=?,notes=?
            WHERE id=?
        """, (rec.name, rec.description, rec.category, rec.total_servings, rec.notes, recipe_id))
        return {"status": "updated"}

@app.delete("/api/recipes/{recipe_id}")
def delete_recipe(recipe_id: int):
    with db() as conn:
        conn.execute("UPDATE recipes SET is_active=0 WHERE id=?", (recipe_id,))
        return {"status": "deleted"}

@app.post("/api/recipes/{recipe_id}/components", status_code=201)
def add_recipe_component(recipe_id: int, comp: RecipeComponentIn):
    with db() as conn:
        recipe = conn.execute("SELECT id FROM recipes WHERE id=?", (recipe_id,)).fetchone()
        if not recipe:
            raise HTTPException(404, "Recipe not found")
        ing = conn.execute("SELECT id FROM ingredients WHERE id=? AND is_active=1", (comp.ingredient_id,)).fetchone()
        if not ing:
            raise HTTPException(404, "Ingredient not found")
        cur = conn.execute(
            "INSERT INTO recipe_components (recipe_id,ingredient_id,quantity) VALUES (?,?,?)",
            (recipe_id, comp.ingredient_id, comp.quantity)
        )
        return {"id": cur.lastrowid}

@app.put("/api/recipes/{recipe_id}/components/{comp_id}")
def update_recipe_component(recipe_id: int, comp_id: int, comp: RecipeComponentIn):
    with db() as conn:
        conn.execute(
            "UPDATE recipe_components SET quantity=? WHERE id=? AND recipe_id=?",
            (comp.quantity, comp_id, recipe_id)
        )
        return {"status": "updated"}

@app.delete("/api/recipes/{recipe_id}/components/{comp_id}")
def delete_recipe_component(recipe_id: int, comp_id: int):
    with db() as conn:
        conn.execute("DELETE FROM recipe_components WHERE id=? AND recipe_id=?", (comp_id, recipe_id))
        return {"status": "deleted"}

# ── API: Food Search ──────────────────────────────────────────────────────────

@app.get("/api/food/search")
def search_food(q: str = Query("", min_length=0)):
    with db() as conn:
        results = []
        # Ingredients
        ing_rows = conn.execute("""
            SELECT id, name, brand, category, serving_size, serving_unit,
                   calories, protein, carbs, fat, fiber
            FROM ingredients
            WHERE is_active=1 AND (name LIKE ? OR brand LIKE ?)
            ORDER BY name LIMIT 20
        """, (f"%{q}%", f"%{q}%")).fetchall()
        for r in ing_rows:
            d = dict(r)
            d["type"] = "ingredient"
            d["display_name"] = f"{d['name']}" + (f" ({d['brand']})" if d["brand"] else "")
            d["macros_per_serving"] = {
                "calories": d["calories"], "protein": d["protein"],
                "carbs": d["carbs"], "fat": d["fat"], "fiber": d["fiber"]
            }
            results.append(d)
        # Recipes
        rec_rows = conn.execute("""
            SELECT id, name, description, category, total_servings
            FROM recipes
            WHERE is_active=1 AND name LIKE ?
            ORDER BY name LIMIT 20
        """, (f"%{q}%",)).fetchall()
        for r in rec_rows:
            d = dict(r)
            d["type"] = "recipe"
            d["display_name"] = d["name"]
            d["macros_per_serving"] = macros_per_serving_for_recipe(conn, d["id"])
            results.append(d)
        return sorted(results, key=lambda x: x["display_name"])

# ── API: Food Log ─────────────────────────────────────────────────────────────

@app.get("/api/log")
def get_log(date_str: str = Query(..., alias="date")):
    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM food_log WHERE date=? ORDER BY created_at",
            (date_str,)
        ).fetchall()
        return [dict(r) for r in rows]

@app.post("/api/log", status_code=201)
def add_log_entry(entry: FoodLogIn):
    with db() as conn:
        # Compute macros at log time
        if entry.food_type == "ingredient":
            ing = conn.execute("SELECT * FROM ingredients WHERE id=?", (entry.food_id,)).fetchone()
            if not ing:
                raise HTTPException(404, "Ingredient not found")
            s = entry.servings
            calories = round(ing["calories"] * s, 2)
            protein  = round(ing["protein"]  * s, 2)
            carbs    = round(ing["carbs"]    * s, 2)
            fat      = round(ing["fat"]      * s, 2)
            fiber    = round((ing["fiber"] or 0) * s, 2)
            name = ing["name"] + (f" ({ing['brand']})" if ing["brand"] else "")
        elif entry.food_type == "recipe":
            rec = conn.execute("SELECT * FROM recipes WHERE id=?", (entry.food_id,)).fetchone()
            if not rec:
                raise HTTPException(404, "Recipe not found")
            mps = macros_per_serving_for_recipe(conn, entry.food_id)
            s = entry.servings
            calories = round(mps.get("calories", 0) * s, 2)
            protein  = round(mps.get("protein",  0) * s, 2)
            carbs    = round(mps.get("carbs",    0) * s, 2)
            fat      = round(mps.get("fat",      0) * s, 2)
            fiber    = round(mps.get("fiber",    0) * s, 2)
            name = rec["name"]
        else:
            raise HTTPException(400, "food_type must be 'ingredient' or 'recipe'")

        cur = conn.execute("""
            INSERT INTO food_log
              (date,meal_type,food_type,food_id,food_name,servings,calories,protein,carbs,fat,fiber,notes)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """, (entry.date, entry.meal_type, entry.food_type, entry.food_id, name,
              entry.servings, calories, protein, carbs, fat, fiber, entry.notes))
        return {"id": cur.lastrowid, "calories": calories, "protein": protein,
                "carbs": carbs, "fat": fat}

@app.delete("/api/log/{log_id}")
def delete_log_entry(log_id: int):
    with db() as conn:
        conn.execute("DELETE FROM food_log WHERE id=?", (log_id,))
        return {"status": "deleted"}

# ── API: Body Config ──────────────────────────────────────────────────────────

@app.get("/api/body/config")
def list_body_config():
    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM body_config WHERE is_active=1 ORDER BY position, id"
        ).fetchall()
        return [dict(r) for r in rows]

@app.post("/api/body/config", status_code=201)
def create_body_config(cfg: BodyConfigIn):
    with db() as conn:
        existing = conn.execute("SELECT id FROM body_config WHERE key=?", (cfg.key,)).fetchone()
        if existing:
            raise HTTPException(400, f"Key '{cfg.key}' already exists")
        pos = conn.execute("SELECT COALESCE(MAX(position),0)+1 FROM body_config").fetchone()[0]
        conn.execute(
            "INSERT INTO body_config (key,label,unit,category,target_value,position) VALUES (?,?,?,?,?,?)",
            (cfg.key, cfg.label, cfg.unit, cfg.category, cfg.target_value, pos)
        )
        return {"status": "created", "key": cfg.key}

@app.put("/api/body/config/{key}")
def update_body_config(key: str, upd: BodyConfigUpdateIn):
    with db() as conn:
        row = conn.execute("SELECT * FROM body_config WHERE key=?", (key,)).fetchone()
        if not row:
            raise HTTPException(404, "Config not found")
        fields = {}
        if upd.label is not None:       fields["label"] = upd.label
        if upd.unit is not None:        fields["unit"] = upd.unit
        if upd.target_value is not None: fields["target_value"] = upd.target_value
        if upd.is_active is not None:   fields["is_active"] = upd.is_active
        if fields:
            set_clause = ", ".join(f"{k}=?" for k in fields)
            conn.execute(
                f"UPDATE body_config SET {set_clause} WHERE key=?",
                list(fields.values()) + [key]
            )
        return {"status": "updated"}

@app.delete("/api/body/config/{key}")
def delete_body_config(key: str):
    with db() as conn:
        conn.execute("UPDATE body_config SET is_active=0 WHERE key=?", (key,))
        return {"status": "deleted"}

# ── API: Body Measurements ────────────────────────────────────────────────────

@app.get("/api/body/measurements")
def get_measurements(
    start: str = Query(default=""),
    end: str = Query(default=""),
    key: str = Query(default="")
):
    with db() as conn:
        sql = "SELECT * FROM body_measurements WHERE 1=1"
        params = []
        if start:
            sql += " AND date >= ?"
            params.append(start)
        if end:
            sql += " AND date <= ?"
            params.append(end)
        if key:
            sql += " AND measurable_key = ?"
            params.append(key)
        sql += " ORDER BY date DESC"
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

@app.post("/api/body/measurements", status_code=201)
def log_measurement(m: BodyMeasurementIn):
    with db() as conn:
        conn.execute("""
            INSERT INTO body_measurements (date, measurable_key, value)
            VALUES (?,?,?)
            ON CONFLICT(date, measurable_key) DO UPDATE SET value=excluded.value
        """, (m.date, m.measurable_key, m.value))
        return {"status": "saved"}

@app.delete("/api/body/measurements/{meas_id}")
def delete_measurement(meas_id: int):
    with db() as conn:
        conn.execute("DELETE FROM body_measurements WHERE id=?", (meas_id,))
        return {"status": "deleted"}

# ── API: Macro Targets ────────────────────────────────────────────────────────

@app.get("/api/targets")
def get_targets():
    with db() as conn:
        row = conn.execute("SELECT * FROM macro_targets ORDER BY id DESC LIMIT 1").fetchone()
        return dict(row) if row else {}

@app.post("/api/targets")
def set_targets(t: MacroTargetsIn):
    with db() as conn:
        conn.execute("""
            INSERT INTO macro_targets (calories,protein,carbs,fat,fiber,updated_at)
            VALUES (?,?,?,?,?,datetime('now'))
        """, (t.calories, t.protein, t.carbs, t.fat, t.fiber))
        return {"status": "saved"}

# ── API: Workouts ─────────────────────────────────────────────────────────────

@app.get("/api/workouts")
def list_workouts(
    date_str: str = Query(default="", alias="date"),
    days: int = Query(default=30)
):
    with db() as conn:
        if date_str:
            rows = conn.execute(
                "SELECT * FROM workouts WHERE date=? ORDER BY created_at", (date_str,)
            ).fetchall()
        else:
            cutoff = (date.today() - timedelta(days=days)).isoformat()
            rows = conn.execute(
                "SELECT * FROM workouts WHERE date >= ? ORDER BY date DESC", (cutoff,)
            ).fetchall()
        result = []
        for row in rows:
            w = dict(row)
            exs = conn.execute(
                "SELECT * FROM workout_exercises WHERE workout_id=?", (w["id"],)
            ).fetchall()
            w["exercises"] = [dict(e) for e in exs]
            result.append(w)
        return result

@app.post("/api/workouts", status_code=201)
def create_workout(w: WorkoutIn):
    with db() as conn:
        cur = conn.execute("""
            INSERT INTO workouts (date,name,workout_type,duration_minutes,calories_burned,notes)
            VALUES (?,?,?,?,?,?)
        """, (w.date, w.name, w.workout_type, w.duration_minutes, w.calories_burned, w.notes))
        return {"id": cur.lastrowid}

@app.put("/api/workouts/{workout_id}")
def update_workout(workout_id: int, w: WorkoutIn):
    with db() as conn:
        conn.execute("""
            UPDATE workouts SET date=?,name=?,workout_type=?,duration_minutes=?,calories_burned=?,notes=?
            WHERE id=?
        """, (w.date, w.name, w.workout_type, w.duration_minutes, w.calories_burned, w.notes, workout_id))
        return {"status": "updated"}

@app.delete("/api/workouts/{workout_id}")
def delete_workout(workout_id: int):
    with db() as conn:
        conn.execute("DELETE FROM workouts WHERE id=?", (workout_id,))
        return {"status": "deleted"}

@app.post("/api/workouts/{workout_id}/exercises", status_code=201)
def add_exercise(workout_id: int, ex: ExerciseIn):
    with db() as conn:
        cur = conn.execute("""
            INSERT INTO workout_exercises
              (workout_id,exercise_name,sets,reps,weight,weight_unit,
               duration_seconds,distance,distance_unit,notes)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (workout_id, ex.exercise_name, ex.sets, ex.reps, ex.weight, ex.weight_unit,
              ex.duration_seconds, ex.distance, ex.distance_unit, ex.notes))
        return {"id": cur.lastrowid}

@app.delete("/api/workouts/{workout_id}/exercises/{ex_id}")
def delete_exercise(workout_id: int, ex_id: int):
    with db() as conn:
        conn.execute("DELETE FROM workout_exercises WHERE id=? AND workout_id=?", (ex_id, workout_id))
        return {"status": "deleted"}

# ── API: Analytics ────────────────────────────────────────────────────────────

@app.get("/api/analytics/daily")
def daily_summary(date_str: str = Query(..., alias="date")):
    with db() as conn:
        rows = conn.execute("SELECT * FROM food_log WHERE date=?", (date_str,)).fetchall()
        total = dict(calories=0.0, protein=0.0, carbs=0.0, fat=0.0, fiber=0.0)
        by_meal = {}
        for r in rows:
            mt = r["meal_type"]
            if mt not in by_meal:
                by_meal[mt] = dict(calories=0.0, protein=0.0, carbs=0.0, fat=0.0, fiber=0.0, items=[])
            for k in ("calories", "protein", "carbs", "fat", "fiber"):
                by_meal[mt][k] += r[k] or 0
                total[k] += r[k] or 0
            by_meal[mt]["items"].append(dict(r))

        # Get targets
        tgt = conn.execute("SELECT * FROM macro_targets ORDER BY id DESC LIMIT 1").fetchone()
        targets = dict(tgt) if tgt else {}

        # Workouts for today
        workouts = conn.execute(
            "SELECT name, workout_type, duration_minutes, calories_burned FROM workouts WHERE date=?",
            (date_str,)
        ).fetchall()

        return {
            "date": date_str,
            "totals": {k: round(v, 1) for k, v in total.items()},
            "by_meal": by_meal,
            "targets": targets,
            "workouts": [dict(w) for w in workouts],
        }

@app.get("/api/analytics/macro-trends")
def macro_trends(days: int = Query(30, ge=7, le=365)):
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    with db() as conn:
        rows = conn.execute("""
            SELECT date,
                   SUM(calories) as calories,
                   SUM(protein)  as protein,
                   SUM(carbs)    as carbs,
                   SUM(fat)      as fat,
                   SUM(fiber)    as fiber
            FROM food_log
            WHERE date >= ?
            GROUP BY date
            ORDER BY date
        """, (cutoff,)).fetchall()
        return [dict(r) for r in rows]

@app.get("/api/analytics/body-trends")
def body_trends(days: int = Query(90, ge=7, le=365)):
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    with db() as conn:
        rows = conn.execute("""
            SELECT bm.date, bm.measurable_key, bm.value, bc.label, bc.unit, bc.target_value
            FROM body_measurements bm
            JOIN body_config bc ON bc.key = bm.measurable_key
            WHERE bm.date >= ?
            ORDER BY bm.date
        """, (cutoff,)).fetchall()
        return [dict(r) for r in rows]

# ── API: AI ───────────────────────────────────────────────────────────────────

@app.post("/api/ai/food-lookup")
def ai_food_lookup(body: dict):
    if not ANTHROPIC_AVAILABLE:
        raise HTTPException(503, "anthropic package not installed")
    if not ANTHROPIC_API_KEY:
        raise HTTPException(503, "ANTHROPIC_API_KEY not set")

    food_name = body.get("name", "")
    if not food_name:
        raise HTTPException(400, "name is required")

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    try:
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            messages=[{
                "role": "user",
                "content": f"""For the food item "{food_name}", return typical nutritional info per standard serving.
Return ONLY valid JSON with these exact keys:
serving_size (number), serving_unit (string: g/ml/cup/piece/tbsp),
calories, protein, carbs, fat, fiber, sugar, sodium
All macro values are numbers in grams (sodium in mg). No explanation, only JSON."""
            }]
        )
    except anthropic.AuthenticationError:
        raise HTTPException(401, "Invalid API key — check ANTHROPIC_API_KEY")
    except Exception as e:
        raise HTTPException(502, f"Anthropic API error: {e}")
    try:
        text = msg.content[0].text.strip()
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text)
    except Exception:
        raise HTTPException(500, "AI returned unparseable response")

@app.post("/api/ai/analyze")
def ai_analyze():
    if not ANTHROPIC_AVAILABLE:
        raise HTTPException(503, "anthropic package not installed")
    if not ANTHROPIC_API_KEY:
        raise HTTPException(503, "ANTHROPIC_API_KEY not set")

    cutoff = (date.today() - timedelta(days=7)).isoformat()
    with db() as conn:
        macro_rows = conn.execute("""
            SELECT date, SUM(calories) cal, SUM(protein) pro, SUM(carbs) carb, SUM(fat) fat
            FROM food_log WHERE date >= ? GROUP BY date ORDER BY date
        """, (cutoff,)).fetchall()
        tgt = conn.execute("SELECT * FROM macro_targets ORDER BY id DESC LIMIT 1").fetchone()
        body_rows = conn.execute("""
            SELECT bm.date, bc.label, bm.value, bc.unit, bc.target_value
            FROM body_measurements bm JOIN body_config bc ON bc.key=bm.measurable_key
            WHERE bm.date >= ? ORDER BY bm.date
        """, (cutoff,)).fetchall()
        workout_rows = conn.execute("""
            SELECT date, name, workout_type, duration_minutes FROM workouts
            WHERE date >= ? ORDER BY date
        """, (cutoff,)).fetchall()

    if not macro_rows:
        raise HTTPException(400, "No food log data in the last 7 days")

    targets_str = ""
    if tgt:
        targets_str = f"\nTargets: {tgt['calories']} cal | {tgt['protein']}g protein | {tgt['carbs']}g carbs | {tgt['fat']}g fat"

    nutrition_lines = [
        f"{r['date']}: {round(r['cal'] or 0)} cal, {round(r['pro'] or 0)}g protein, "
        f"{round(r['carb'] or 0)}g carbs, {round(r['fat'] or 0)}g fat"
        for r in macro_rows
    ]
    body_lines = [f"{r['date']} {r['label']}: {r['value']}{r['unit']}" for r in body_rows]
    workout_lines = [
        f"{r['date']}: {r['name']} ({r['workout_type']}, {r['duration_minutes'] or '?'} min)"
        for r in workout_rows
    ]

    prompt = f"""You are a personal nutrition and fitness coach. Analyze the last 7 days of data.

NUTRITION:{targets_str}
{chr(10).join(nutrition_lines)}

BODY MEASUREMENTS:
{chr(10).join(body_lines) if body_lines else "None logged"}

WORKOUTS:
{chr(10).join(workout_lines) if workout_lines else "None logged"}

Write a concise weekly analysis (3-4 paragraphs) covering:
1. Nutrition patterns vs targets (highlight gaps and wins)
2. Body composition changes or trends
3. Workout consistency and intensity
4. 2-3 specific, actionable recommendations for next week

Be direct, warm, and specific. Prose only — no bullet points. Under 280 words."""

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    try:
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}]
        )
    except anthropic.AuthenticationError:
        raise HTTPException(401, "Invalid API key — check ANTHROPIC_API_KEY")
    except Exception as e:
        raise HTTPException(502, f"Anthropic API error: {e}")
    content = msg.content[0].text

    with db() as conn:
        conn.execute(
            "INSERT INTO ai_insights (week_start, content) VALUES (?,?)",
            (cutoff, content)
        )
    return {"content": content}

@app.get("/api/ai/latest-insight")
def latest_insight():
    with db() as conn:
        row = conn.execute("SELECT * FROM ai_insights ORDER BY created_at DESC LIMIT 1").fetchone()
        return dict(row) if row else {"content": None}

# ── API: Computed Body Metrics ────────────────────────────────────────────────

@app.get("/api/body/computed")
def computed_body_metrics():
    """Auto-calculate BMI, Navy body fat %, lean mass from latest measurements."""
    with db() as conn:
        # Fetch latest value for each relevant key
        keys = ["weight", "height", "waist", "neck", "hips", "body_fat_pct"]
        latest = {}
        for key in keys:
            row = conn.execute(
                "SELECT value FROM body_measurements WHERE measurable_key=? ORDER BY date DESC LIMIT 1",
                (key,)
            ).fetchone()
            if row:
                latest[key] = row["value"]

    results = {}

    # ── BMI (lbs + inches) ─────────────────────────────────────────────────────
    if "weight" in latest and "height" in latest:
        h = latest["height"]
        bmi = (latest["weight"] / (h ** 2)) * 703
        results["bmi"] = round(bmi, 1)
        if   bmi < 18.5: results["bmi_category"] = "Underweight"
        elif bmi < 25.0: results["bmi_category"] = "Normal weight"
        elif bmi < 30.0: results["bmi_category"] = "Overweight"
        else:            results["bmi_category"] = "Obese"

    # ── Navy Body Fat % — Male (waist, neck, height all in inches) ─────────────
    if all(k in latest for k in ["waist", "neck", "height"]):
        diff = latest["waist"] - latest["neck"]
        if diff > 0:
            bf_m = 86.010 * math.log10(diff) - 70.041 * math.log10(latest["height"]) + 36.76
            results["navy_bf_male"] = round(bf_m, 1)

    # ── Navy Body Fat % — Female (waist + hips, neck, height) ─────────────────
    if all(k in latest for k in ["waist", "hips", "neck", "height"]):
        diff = latest["waist"] + latest["hips"] - latest["neck"]
        if diff > 0:
            bf_f = 163.205 * math.log10(diff) - 97.684 * math.log10(latest["height"]) - 78.387
            results["navy_bf_female"] = round(bf_f, 1)

    # ── Lean & Fat Mass (uses logged BF% first, then Navy male estimate) ────────
    bf_pct = latest.get("body_fat_pct") or results.get("navy_bf_male")
    if "weight" in latest and bf_pct:
        fat_mass  = round(latest["weight"] * (bf_pct / 100), 1)
        lean_mass = round(latest["weight"] - fat_mass, 1)
        results["fat_mass_lbs"]  = fat_mass
        results["lean_mass_lbs"] = lean_mass

    # ── Ideal body weight (Devine formula, inches) ─────────────────────────────
    if "height" in latest:
        h_over_5ft = max(0, latest["height"] - 60)
        results["ibw_male_lbs"]   = round(110 + 5.0 * h_over_5ft, 1)
        results["ibw_female_lbs"] = round( 100 + 5.0 * h_over_5ft, 1)

    results["inputs"] = latest
    return results

# ── API: AI Body Composition Estimator ───────────────────────────────────────

class BodyEstimateIn(BaseModel):
    description: str
    weight_lbs: Optional[float] = None
    height_in: Optional[float] = None
    age: Optional[int] = None
    sex: Optional[str] = None  # 'male' or 'female'

@app.post("/api/ai/body-estimate")
def ai_body_estimate(body: BodyEstimateIn):
    if not ANTHROPIC_AVAILABLE:
        raise HTTPException(503, "anthropic package not installed")
    if not ANTHROPIC_API_KEY:
        raise HTTPException(503, "ANTHROPIC_API_KEY not set")

    context_lines = []
    if body.weight_lbs: context_lines.append(f"Weight: {body.weight_lbs} lbs")
    if body.height_in:  context_lines.append(f"Height: {body.height_in} in")
    if body.age:        context_lines.append(f"Age: {body.age}")
    if body.sex:        context_lines.append(f"Sex: {body.sex}")

    prompt = f"""You are a certified fitness coach and body composition specialist. Estimate body composition from the description below.

Physical description: "{body.description}"
{chr(10).join(context_lines) if context_lines else "No stats provided."}

Return ONLY a JSON object with these exact keys:
- body_fat_pct: number (point estimate)
- body_fat_range: string (e.g. "14-17%")
- body_fat_category: string (one of: "Essential Fat", "Athletic", "Fitness", "Average", "Above Average")
- ffmi: number or null (Fat-Free Mass Index if weight+height provided, else null)
- muscle_assessment: string (one sentence on muscularity/development)
- notes: string (2-3 sentences: reasoning, confidence level, key caveats)
- suggestions: string (1-2 specific, actionable next steps)

No markdown, no explanation — only the JSON object."""

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    try:
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}]
        )
    except anthropic.AuthenticationError:
        raise HTTPException(401, "Invalid API key — check ANTHROPIC_API_KEY")
    except Exception as e:
        raise HTTPException(502, f"Anthropic API error: {e}")

    text = msg.content[0].text.strip()
    # Strip markdown fences if present
    if "```" in text:
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    try:
        return json.loads(text)
    except Exception:
        raise HTTPException(500, "AI returned an unparseable response")

# ── Serve Frontend ────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def serve_frontend():
    html_path = Path(__file__).parent / "static" / "index.html"
    return HTMLResponse(html_path.read_text())

# ── Boot ──────────────────────────────────────────────────────────────────────

def migrate_db():
    """One-time migrations to keep existing installs up to date."""
    with db() as conn:
        # Migrate cm → in and kg → lbs for existing seeded records
        unit_map = {
            "weight": "lbs", "height": "in", "muscle_mass": "lbs",
            "neck": "in", "waist": "in", "hips": "in",
            "chest": "in", "left_arm": "in", "right_arm": "in",
            "left_thigh": "in", "right_thigh": "in",
        }
        for key, unit in unit_map.items():
            conn.execute(
                "UPDATE body_config SET unit=? WHERE key=? AND unit IN ('cm','kg')",
                (unit, key)
            )
        # Add height and neck if missing
        for key, label, unit, cat, pos in [
            ("height", "Height", "in", "weight",      1),
            ("neck",   "Neck",   "in", "measurement", 4),
        ]:
            exists = conn.execute("SELECT id FROM body_config WHERE key=?", (key,)).fetchone()
            if not exists:
                conn.execute(
                    "INSERT INTO body_config (key,label,unit,category,position) VALUES (?,?,?,?,?)",
                    (key, label, unit, cat, pos)
                )

if __name__ == "__main__":
    init_db()
    migrate_db()
    print("\n  Macro Tracker running at http://localhost:8001")
    print("  API docs at http://localhost:8001/api/docs\n")
    uvicorn.run(app, host="127.0.0.1", port=8001, log_level="warning")
