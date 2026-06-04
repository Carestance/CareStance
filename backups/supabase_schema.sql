


SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;


COMMENT ON SCHEMA "public" IS 'standard public schema';



CREATE EXTENSION IF NOT EXISTS "pg_graphql" WITH SCHEMA "graphql";






CREATE EXTENSION IF NOT EXISTS "pg_stat_statements" WITH SCHEMA "extensions";






CREATE EXTENSION IF NOT EXISTS "pgcrypto" WITH SCHEMA "extensions";






CREATE EXTENSION IF NOT EXISTS "supabase_vault" WITH SCHEMA "vault";






CREATE EXTENSION IF NOT EXISTS "uuid-ossp" WITH SCHEMA "extensions";





SET default_tablespace = '';

SET default_table_access_method = "heap";


CREATE TABLE IF NOT EXISTS "public"."appointments" (
    "id" integer NOT NULL,
    "student_id" integer,
    "counsellor_id" integer,
    "appointment_time" timestamp without time zone,
    "status" character varying,
    "payment_status" character varying,
    "meeting_link" character varying,
    "razorpay_order_id" character varying,
    "razorpay_payment_id" character varying,
    "counsellor_joined" boolean,
    "joined_at" timestamp without time zone,
    "student_joined" boolean,
    "student_joined_at" timestamp without time zone,
    "actual_overlap_minutes" integer
);


ALTER TABLE "public"."appointments" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "public"."appointments_id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE "public"."appointments_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "public"."appointments_id_seq" OWNED BY "public"."appointments"."id";



CREATE TABLE IF NOT EXISTS "public"."assessment_results" (
    "id" integer NOT NULL,
    "user_id" integer,
    "phase_2_category" character varying,
    "personality" character varying,
    "goal_status" character varying,
    "confidence" double precision,
    "reasoning" "text",
    "raw_answers" json,
    "selected_class" character varying,
    "phase3_result" character varying,
    "phase3_answers" json,
    "phase3_analysis" "text",
    "final_answers" json,
    "stream_scores" json,
    "recommended_stream" character varying,
    "final_analysis" "text",
    "stream_pros" json,
    "stream_cons" json,
    "simulation_career" character varying,
    "simulation_questions" json,
    "simulation_answers" json,
    "simulation_evaluation" json
);


ALTER TABLE "public"."assessment_results" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "public"."assessment_results_id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE "public"."assessment_results_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "public"."assessment_results_id_seq" OWNED BY "public"."assessment_results"."id";



CREATE TABLE IF NOT EXISTS "public"."career_paths" (
    "id" integer NOT NULL,
    "user_id" integer,
    "career_title" character varying,
    "path_data" json,
    "reminders" json,
    "created_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."career_paths" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "public"."career_paths_id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE "public"."career_paths_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "public"."career_paths_id_seq" OWNED BY "public"."career_paths"."id";



CREATE TABLE IF NOT EXISTS "public"."chat_messages" (
    "id" integer NOT NULL,
    "user_id" integer,
    "sender" character varying,
    "content" "text",
    "timestamp" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."chat_messages" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "public"."chat_messages_id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE "public"."chat_messages_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "public"."chat_messages_id_seq" OWNED BY "public"."chat_messages"."id";



CREATE TABLE IF NOT EXISTS "public"."college_recommendations" (
    "id" integer NOT NULL,
    "user_id" integer,
    "career_title" character varying,
    "college_data" json,
    "created_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."college_recommendations" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "public"."college_recommendations_id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE "public"."college_recommendations_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "public"."college_recommendations_id_seq" OWNED BY "public"."college_recommendations"."id";



CREATE TABLE IF NOT EXISTS "public"."counsellor_profiles" (
    "id" integer NOT NULL,
    "user_id" integer,
    "fee" double precision,
    "availability" json,
    "account_details" json,
    "certificates" json,
    "experience" "text",
    "average_rating" double precision,
    "rating_count" integer,
    "is_verified" boolean,
    "verification_status" character varying,
    "tnc_accepted" boolean,
    "tnc_accepted_at" timestamp without time zone,
    "is_blocked" boolean,
    "block_reason" character varying,
    "fee_locked" boolean,
    "razorpay_account_id" character varying,
    "onboarding_status" character varying,
    "razorpay_contact_id" character varying,
    "razorpay_fund_account_id" character varying,
    "is_founding_counsellor" boolean,
    "founding_badge_awarded_at" timestamp without time zone,
    "commission_free_until" timestamp without time zone
);


ALTER TABLE "public"."counsellor_profiles" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "public"."counsellor_profiles_id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE "public"."counsellor_profiles_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "public"."counsellor_profiles_id_seq" OWNED BY "public"."counsellor_profiles"."id";



CREATE TABLE IF NOT EXISTS "public"."counsellor_ratings" (
    "id" integer NOT NULL,
    "appointment_id" integer,
    "counsellor_id" integer,
    "student_id" integer,
    "rating" integer NOT NULL,
    "review" "text",
    "timestamp" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."counsellor_ratings" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "public"."counsellor_ratings_id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE "public"."counsellor_ratings_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "public"."counsellor_ratings_id_seq" OWNED BY "public"."counsellor_ratings"."id";



CREATE TABLE IF NOT EXISTS "public"."feedbacks" (
    "id" integer NOT NULL,
    "user_id" integer,
    "content" "text",
    "rating" integer,
    "timestamp" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."feedbacks" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "public"."feedbacks_id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE "public"."feedbacks_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "public"."feedbacks_id_seq" OWNED BY "public"."feedbacks"."id";



CREATE TABLE IF NOT EXISTS "public"."moderation_flags" (
    "id" integer NOT NULL,
    "user_id" integer,
    "content" "text",
    "chat_type" character varying,
    "status" character varying,
    "timestamp" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."moderation_flags" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "public"."moderation_flags_id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE "public"."moderation_flags_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "public"."moderation_flags_id_seq" OWNED BY "public"."moderation_flags"."id";



CREATE TABLE IF NOT EXISTS "public"."notifications" (
    "id" integer NOT NULL,
    "user_id" integer,
    "type" character varying,
    "message" "text",
    "is_read" boolean,
    "created_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."notifications" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "public"."notifications_id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE "public"."notifications_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "public"."notifications_id_seq" OWNED BY "public"."notifications"."id";



CREATE TABLE IF NOT EXISTS "public"."payments" (
    "id" integer NOT NULL,
    "session_id" integer,
    "razorpay_order_id" character varying,
    "razorpay_payment_id" character varying,
    "amount" double precision,
    "currency" character varying,
    "status" character varying,
    "created_at" timestamp with time zone DEFAULT "now"(),
    "updated_at" timestamp with time zone
);


ALTER TABLE "public"."payments" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "public"."payments_id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE "public"."payments_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "public"."payments_id_seq" OWNED BY "public"."payments"."id";



CREATE TABLE IF NOT EXISTS "public"."student_connections" (
    "id" integer NOT NULL,
    "requester_id" integer,
    "receiver_id" integer,
    "status" character varying,
    "created_at" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."student_connections" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "public"."student_connections_id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE "public"."student_connections_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "public"."student_connections_id_seq" OWNED BY "public"."student_connections"."id";



CREATE TABLE IF NOT EXISTS "public"."student_messages" (
    "id" integer NOT NULL,
    "sender_id" integer,
    "receiver_id" integer,
    "content" "text",
    "attachment_path" character varying,
    "attachment_type" character varying,
    "timestamp" timestamp with time zone DEFAULT "now"(),
    "is_read" boolean
);


ALTER TABLE "public"."student_messages" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "public"."student_messages_id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE "public"."student_messages_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "public"."student_messages_id_seq" OWNED BY "public"."student_messages"."id";



CREATE TABLE IF NOT EXISTS "public"."tickets" (
    "id" integer NOT NULL,
    "user_id" integer,
    "subject" character varying,
    "description" "text",
    "status" character varying,
    "admin_reply" "text",
    "timestamp" timestamp with time zone DEFAULT "now"()
);


ALTER TABLE "public"."tickets" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "public"."tickets_id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE "public"."tickets_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "public"."tickets_id_seq" OWNED BY "public"."tickets"."id";



CREATE TABLE IF NOT EXISTS "public"."transfers" (
    "id" integer NOT NULL,
    "payment_id" integer,
    "counsellor_id" integer,
    "amount" double precision,
    "razorpay_transfer_id" character varying,
    "status" character varying,
    "created_at" timestamp with time zone DEFAULT "now"(),
    "updated_at" timestamp with time zone
);


ALTER TABLE "public"."transfers" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "public"."transfers_id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE "public"."transfers_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "public"."transfers_id_seq" OWNED BY "public"."transfers"."id";



CREATE TABLE IF NOT EXISTS "public"."users" (
    "id" integer NOT NULL,
    "email" character varying,
    "hashed_password" character varying,
    "full_name" character varying,
    "contact_number" character varying,
    "profile_photo" character varying,
    "bio" "text",
    "role" character varying,
    "is_suspended" boolean,
    "onboarded" boolean DEFAULT false
);


ALTER TABLE "public"."users" OWNER TO "postgres";


CREATE SEQUENCE IF NOT EXISTS "public"."users_id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE "public"."users_id_seq" OWNER TO "postgres";


ALTER SEQUENCE "public"."users_id_seq" OWNED BY "public"."users"."id";



ALTER TABLE ONLY "public"."appointments" ALTER COLUMN "id" SET DEFAULT "nextval"('"public"."appointments_id_seq"'::"regclass");



ALTER TABLE ONLY "public"."assessment_results" ALTER COLUMN "id" SET DEFAULT "nextval"('"public"."assessment_results_id_seq"'::"regclass");



ALTER TABLE ONLY "public"."career_paths" ALTER COLUMN "id" SET DEFAULT "nextval"('"public"."career_paths_id_seq"'::"regclass");



ALTER TABLE ONLY "public"."chat_messages" ALTER COLUMN "id" SET DEFAULT "nextval"('"public"."chat_messages_id_seq"'::"regclass");



ALTER TABLE ONLY "public"."college_recommendations" ALTER COLUMN "id" SET DEFAULT "nextval"('"public"."college_recommendations_id_seq"'::"regclass");



ALTER TABLE ONLY "public"."counsellor_profiles" ALTER COLUMN "id" SET DEFAULT "nextval"('"public"."counsellor_profiles_id_seq"'::"regclass");



ALTER TABLE ONLY "public"."counsellor_ratings" ALTER COLUMN "id" SET DEFAULT "nextval"('"public"."counsellor_ratings_id_seq"'::"regclass");



ALTER TABLE ONLY "public"."feedbacks" ALTER COLUMN "id" SET DEFAULT "nextval"('"public"."feedbacks_id_seq"'::"regclass");



ALTER TABLE ONLY "public"."moderation_flags" ALTER COLUMN "id" SET DEFAULT "nextval"('"public"."moderation_flags_id_seq"'::"regclass");



ALTER TABLE ONLY "public"."notifications" ALTER COLUMN "id" SET DEFAULT "nextval"('"public"."notifications_id_seq"'::"regclass");



ALTER TABLE ONLY "public"."payments" ALTER COLUMN "id" SET DEFAULT "nextval"('"public"."payments_id_seq"'::"regclass");



ALTER TABLE ONLY "public"."student_connections" ALTER COLUMN "id" SET DEFAULT "nextval"('"public"."student_connections_id_seq"'::"regclass");



ALTER TABLE ONLY "public"."student_messages" ALTER COLUMN "id" SET DEFAULT "nextval"('"public"."student_messages_id_seq"'::"regclass");



ALTER TABLE ONLY "public"."tickets" ALTER COLUMN "id" SET DEFAULT "nextval"('"public"."tickets_id_seq"'::"regclass");



ALTER TABLE ONLY "public"."transfers" ALTER COLUMN "id" SET DEFAULT "nextval"('"public"."transfers_id_seq"'::"regclass");



ALTER TABLE ONLY "public"."users" ALTER COLUMN "id" SET DEFAULT "nextval"('"public"."users_id_seq"'::"regclass");



ALTER TABLE ONLY "public"."appointments"
    ADD CONSTRAINT "appointments_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."assessment_results"
    ADD CONSTRAINT "assessment_results_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."career_paths"
    ADD CONSTRAINT "career_paths_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."chat_messages"
    ADD CONSTRAINT "chat_messages_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."college_recommendations"
    ADD CONSTRAINT "college_recommendations_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."counsellor_profiles"
    ADD CONSTRAINT "counsellor_profiles_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."counsellor_ratings"
    ADD CONSTRAINT "counsellor_ratings_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."feedbacks"
    ADD CONSTRAINT "feedbacks_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."moderation_flags"
    ADD CONSTRAINT "moderation_flags_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."notifications"
    ADD CONSTRAINT "notifications_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."payments"
    ADD CONSTRAINT "payments_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."student_connections"
    ADD CONSTRAINT "student_connections_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."student_messages"
    ADD CONSTRAINT "student_messages_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."tickets"
    ADD CONSTRAINT "tickets_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."transfers"
    ADD CONSTRAINT "transfers_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."transfers"
    ADD CONSTRAINT "transfers_razorpay_transfer_id_key" UNIQUE ("razorpay_transfer_id");



ALTER TABLE ONLY "public"."users"
    ADD CONSTRAINT "users_pkey" PRIMARY KEY ("id");



CREATE INDEX "ix_appointments_appointment_time" ON "public"."appointments" USING "btree" ("appointment_time");



CREATE INDEX "ix_appointments_counsellor_id" ON "public"."appointments" USING "btree" ("counsellor_id");



CREATE INDEX "ix_appointments_id" ON "public"."appointments" USING "btree" ("id");



CREATE INDEX "ix_appointments_payment_status" ON "public"."appointments" USING "btree" ("payment_status");



CREATE INDEX "ix_appointments_status" ON "public"."appointments" USING "btree" ("status");



CREATE INDEX "ix_appointments_student_id" ON "public"."appointments" USING "btree" ("student_id");



CREATE INDEX "ix_assessment_results_id" ON "public"."assessment_results" USING "btree" ("id");



CREATE INDEX "ix_assessment_results_personality" ON "public"."assessment_results" USING "btree" ("personality");



CREATE INDEX "ix_assessment_results_phase_2_category" ON "public"."assessment_results" USING "btree" ("phase_2_category");



CREATE INDEX "ix_assessment_results_recommended_stream" ON "public"."assessment_results" USING "btree" ("recommended_stream");



CREATE INDEX "ix_assessment_results_selected_class" ON "public"."assessment_results" USING "btree" ("selected_class");



CREATE INDEX "ix_assessment_results_user_id" ON "public"."assessment_results" USING "btree" ("user_id");



CREATE INDEX "ix_career_paths_career_title" ON "public"."career_paths" USING "btree" ("career_title");



CREATE INDEX "ix_career_paths_id" ON "public"."career_paths" USING "btree" ("id");



CREATE INDEX "ix_career_paths_user_id" ON "public"."career_paths" USING "btree" ("user_id");



CREATE INDEX "ix_chat_messages_id" ON "public"."chat_messages" USING "btree" ("id");



CREATE INDEX "ix_chat_messages_sender" ON "public"."chat_messages" USING "btree" ("sender");



CREATE INDEX "ix_chat_messages_timestamp" ON "public"."chat_messages" USING "btree" ("timestamp");



CREATE INDEX "ix_chat_messages_user_id" ON "public"."chat_messages" USING "btree" ("user_id");



CREATE INDEX "ix_college_recommendations_career_title" ON "public"."college_recommendations" USING "btree" ("career_title");



CREATE INDEX "ix_college_recommendations_id" ON "public"."college_recommendations" USING "btree" ("id");



CREATE INDEX "ix_college_recommendations_user_id" ON "public"."college_recommendations" USING "btree" ("user_id");



CREATE INDEX "ix_counsellor_profiles_id" ON "public"."counsellor_profiles" USING "btree" ("id");



CREATE INDEX "ix_counsellor_profiles_user_id" ON "public"."counsellor_profiles" USING "btree" ("user_id");



CREATE INDEX "ix_counsellor_profiles_verification_status" ON "public"."counsellor_profiles" USING "btree" ("verification_status");



CREATE UNIQUE INDEX "ix_counsellor_ratings_appointment_id" ON "public"."counsellor_ratings" USING "btree" ("appointment_id");



CREATE INDEX "ix_counsellor_ratings_counsellor_id" ON "public"."counsellor_ratings" USING "btree" ("counsellor_id");



CREATE INDEX "ix_counsellor_ratings_id" ON "public"."counsellor_ratings" USING "btree" ("id");



CREATE INDEX "ix_counsellor_ratings_rating" ON "public"."counsellor_ratings" USING "btree" ("rating");



CREATE INDEX "ix_counsellor_ratings_student_id" ON "public"."counsellor_ratings" USING "btree" ("student_id");



CREATE INDEX "ix_feedbacks_id" ON "public"."feedbacks" USING "btree" ("id");



CREATE INDEX "ix_feedbacks_user_id" ON "public"."feedbacks" USING "btree" ("user_id");



CREATE INDEX "ix_moderation_flags_id" ON "public"."moderation_flags" USING "btree" ("id");



CREATE INDEX "ix_moderation_flags_status" ON "public"."moderation_flags" USING "btree" ("status");



CREATE INDEX "ix_moderation_flags_timestamp" ON "public"."moderation_flags" USING "btree" ("timestamp");



CREATE INDEX "ix_moderation_flags_user_id" ON "public"."moderation_flags" USING "btree" ("user_id");



CREATE INDEX "ix_notifications_created_at" ON "public"."notifications" USING "btree" ("created_at");



CREATE INDEX "ix_notifications_id" ON "public"."notifications" USING "btree" ("id");



CREATE INDEX "ix_notifications_is_read" ON "public"."notifications" USING "btree" ("is_read");



CREATE INDEX "ix_notifications_type" ON "public"."notifications" USING "btree" ("type");



CREATE INDEX "ix_notifications_user_id" ON "public"."notifications" USING "btree" ("user_id");



CREATE INDEX "ix_payments_id" ON "public"."payments" USING "btree" ("id");



CREATE UNIQUE INDEX "ix_payments_razorpay_order_id" ON "public"."payments" USING "btree" ("razorpay_order_id");



CREATE UNIQUE INDEX "ix_payments_razorpay_payment_id" ON "public"."payments" USING "btree" ("razorpay_payment_id");



CREATE INDEX "ix_payments_session_id" ON "public"."payments" USING "btree" ("session_id");



CREATE INDEX "ix_payments_status" ON "public"."payments" USING "btree" ("status");



CREATE INDEX "ix_student_connections_id" ON "public"."student_connections" USING "btree" ("id");



CREATE INDEX "ix_student_connections_receiver_id" ON "public"."student_connections" USING "btree" ("receiver_id");



CREATE INDEX "ix_student_connections_requester_id" ON "public"."student_connections" USING "btree" ("requester_id");



CREATE INDEX "ix_student_connections_status" ON "public"."student_connections" USING "btree" ("status");



CREATE INDEX "ix_student_messages_id" ON "public"."student_messages" USING "btree" ("id");



CREATE INDEX "ix_student_messages_is_read" ON "public"."student_messages" USING "btree" ("is_read");



CREATE INDEX "ix_student_messages_receiver_id" ON "public"."student_messages" USING "btree" ("receiver_id");



CREATE INDEX "ix_student_messages_sender_id" ON "public"."student_messages" USING "btree" ("sender_id");



CREATE INDEX "ix_student_messages_timestamp" ON "public"."student_messages" USING "btree" ("timestamp");



CREATE INDEX "ix_tickets_id" ON "public"."tickets" USING "btree" ("id");



CREATE INDEX "ix_tickets_status" ON "public"."tickets" USING "btree" ("status");



CREATE INDEX "ix_tickets_timestamp" ON "public"."tickets" USING "btree" ("timestamp");



CREATE INDEX "ix_tickets_user_id" ON "public"."tickets" USING "btree" ("user_id");



CREATE INDEX "ix_transfers_counsellor_id" ON "public"."transfers" USING "btree" ("counsellor_id");



CREATE INDEX "ix_transfers_id" ON "public"."transfers" USING "btree" ("id");



CREATE INDEX "ix_transfers_payment_id" ON "public"."transfers" USING "btree" ("payment_id");



CREATE INDEX "ix_transfers_status" ON "public"."transfers" USING "btree" ("status");



CREATE UNIQUE INDEX "ix_users_email" ON "public"."users" USING "btree" ("email");



CREATE INDEX "ix_users_full_name" ON "public"."users" USING "btree" ("full_name");



CREATE INDEX "ix_users_id" ON "public"."users" USING "btree" ("id");



CREATE INDEX "ix_users_onboarded" ON "public"."users" USING "btree" ("onboarded");



CREATE INDEX "ix_users_role" ON "public"."users" USING "btree" ("role");



ALTER TABLE ONLY "public"."appointments"
    ADD CONSTRAINT "appointments_counsellor_id_fkey" FOREIGN KEY ("counsellor_id") REFERENCES "public"."users"("id");



ALTER TABLE ONLY "public"."appointments"
    ADD CONSTRAINT "appointments_student_id_fkey" FOREIGN KEY ("student_id") REFERENCES "public"."users"("id");



ALTER TABLE ONLY "public"."assessment_results"
    ADD CONSTRAINT "assessment_results_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id");



ALTER TABLE ONLY "public"."career_paths"
    ADD CONSTRAINT "career_paths_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id");



ALTER TABLE ONLY "public"."chat_messages"
    ADD CONSTRAINT "chat_messages_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id");



ALTER TABLE ONLY "public"."college_recommendations"
    ADD CONSTRAINT "college_recommendations_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id");



ALTER TABLE ONLY "public"."counsellor_profiles"
    ADD CONSTRAINT "counsellor_profiles_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id");



ALTER TABLE ONLY "public"."counsellor_ratings"
    ADD CONSTRAINT "counsellor_ratings_appointment_id_fkey" FOREIGN KEY ("appointment_id") REFERENCES "public"."appointments"("id");



ALTER TABLE ONLY "public"."counsellor_ratings"
    ADD CONSTRAINT "counsellor_ratings_counsellor_id_fkey" FOREIGN KEY ("counsellor_id") REFERENCES "public"."users"("id");



ALTER TABLE ONLY "public"."counsellor_ratings"
    ADD CONSTRAINT "counsellor_ratings_student_id_fkey" FOREIGN KEY ("student_id") REFERENCES "public"."users"("id");



ALTER TABLE ONLY "public"."feedbacks"
    ADD CONSTRAINT "feedbacks_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id");



ALTER TABLE ONLY "public"."moderation_flags"
    ADD CONSTRAINT "moderation_flags_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id");



ALTER TABLE ONLY "public"."notifications"
    ADD CONSTRAINT "notifications_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id");



ALTER TABLE ONLY "public"."payments"
    ADD CONSTRAINT "payments_session_id_fkey" FOREIGN KEY ("session_id") REFERENCES "public"."appointments"("id");



ALTER TABLE ONLY "public"."student_connections"
    ADD CONSTRAINT "student_connections_receiver_id_fkey" FOREIGN KEY ("receiver_id") REFERENCES "public"."users"("id");



ALTER TABLE ONLY "public"."student_connections"
    ADD CONSTRAINT "student_connections_requester_id_fkey" FOREIGN KEY ("requester_id") REFERENCES "public"."users"("id");



ALTER TABLE ONLY "public"."student_messages"
    ADD CONSTRAINT "student_messages_receiver_id_fkey" FOREIGN KEY ("receiver_id") REFERENCES "public"."users"("id");



ALTER TABLE ONLY "public"."student_messages"
    ADD CONSTRAINT "student_messages_sender_id_fkey" FOREIGN KEY ("sender_id") REFERENCES "public"."users"("id");



ALTER TABLE ONLY "public"."tickets"
    ADD CONSTRAINT "tickets_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id");



ALTER TABLE ONLY "public"."transfers"
    ADD CONSTRAINT "transfers_counsellor_id_fkey" FOREIGN KEY ("counsellor_id") REFERENCES "public"."users"("id");



ALTER TABLE ONLY "public"."transfers"
    ADD CONSTRAINT "transfers_payment_id_fkey" FOREIGN KEY ("payment_id") REFERENCES "public"."payments"("id");





ALTER PUBLICATION "supabase_realtime" OWNER TO "postgres";


GRANT USAGE ON SCHEMA "public" TO "postgres";
GRANT USAGE ON SCHEMA "public" TO "anon";
GRANT USAGE ON SCHEMA "public" TO "authenticated";
GRANT USAGE ON SCHEMA "public" TO "service_role";








































































































































































GRANT ALL ON TABLE "public"."appointments" TO "anon";
GRANT ALL ON TABLE "public"."appointments" TO "authenticated";
GRANT ALL ON TABLE "public"."appointments" TO "service_role";



GRANT ALL ON SEQUENCE "public"."appointments_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."appointments_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."appointments_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."assessment_results" TO "anon";
GRANT ALL ON TABLE "public"."assessment_results" TO "authenticated";
GRANT ALL ON TABLE "public"."assessment_results" TO "service_role";



GRANT ALL ON SEQUENCE "public"."assessment_results_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."assessment_results_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."assessment_results_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."career_paths" TO "anon";
GRANT ALL ON TABLE "public"."career_paths" TO "authenticated";
GRANT ALL ON TABLE "public"."career_paths" TO "service_role";



GRANT ALL ON SEQUENCE "public"."career_paths_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."career_paths_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."career_paths_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."chat_messages" TO "anon";
GRANT ALL ON TABLE "public"."chat_messages" TO "authenticated";
GRANT ALL ON TABLE "public"."chat_messages" TO "service_role";



GRANT ALL ON SEQUENCE "public"."chat_messages_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."chat_messages_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."chat_messages_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."college_recommendations" TO "anon";
GRANT ALL ON TABLE "public"."college_recommendations" TO "authenticated";
GRANT ALL ON TABLE "public"."college_recommendations" TO "service_role";



GRANT ALL ON SEQUENCE "public"."college_recommendations_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."college_recommendations_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."college_recommendations_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."counsellor_profiles" TO "anon";
GRANT ALL ON TABLE "public"."counsellor_profiles" TO "authenticated";
GRANT ALL ON TABLE "public"."counsellor_profiles" TO "service_role";



GRANT ALL ON SEQUENCE "public"."counsellor_profiles_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."counsellor_profiles_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."counsellor_profiles_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."counsellor_ratings" TO "anon";
GRANT ALL ON TABLE "public"."counsellor_ratings" TO "authenticated";
GRANT ALL ON TABLE "public"."counsellor_ratings" TO "service_role";



GRANT ALL ON SEQUENCE "public"."counsellor_ratings_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."counsellor_ratings_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."counsellor_ratings_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."feedbacks" TO "anon";
GRANT ALL ON TABLE "public"."feedbacks" TO "authenticated";
GRANT ALL ON TABLE "public"."feedbacks" TO "service_role";



GRANT ALL ON SEQUENCE "public"."feedbacks_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."feedbacks_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."feedbacks_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."moderation_flags" TO "anon";
GRANT ALL ON TABLE "public"."moderation_flags" TO "authenticated";
GRANT ALL ON TABLE "public"."moderation_flags" TO "service_role";



GRANT ALL ON SEQUENCE "public"."moderation_flags_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."moderation_flags_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."moderation_flags_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."notifications" TO "anon";
GRANT ALL ON TABLE "public"."notifications" TO "authenticated";
GRANT ALL ON TABLE "public"."notifications" TO "service_role";



GRANT ALL ON SEQUENCE "public"."notifications_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."notifications_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."notifications_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."payments" TO "anon";
GRANT ALL ON TABLE "public"."payments" TO "authenticated";
GRANT ALL ON TABLE "public"."payments" TO "service_role";



GRANT ALL ON SEQUENCE "public"."payments_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."payments_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."payments_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."student_connections" TO "anon";
GRANT ALL ON TABLE "public"."student_connections" TO "authenticated";
GRANT ALL ON TABLE "public"."student_connections" TO "service_role";



GRANT ALL ON SEQUENCE "public"."student_connections_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."student_connections_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."student_connections_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."student_messages" TO "anon";
GRANT ALL ON TABLE "public"."student_messages" TO "authenticated";
GRANT ALL ON TABLE "public"."student_messages" TO "service_role";



GRANT ALL ON SEQUENCE "public"."student_messages_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."student_messages_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."student_messages_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."tickets" TO "anon";
GRANT ALL ON TABLE "public"."tickets" TO "authenticated";
GRANT ALL ON TABLE "public"."tickets" TO "service_role";



GRANT ALL ON SEQUENCE "public"."tickets_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."tickets_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."tickets_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."transfers" TO "anon";
GRANT ALL ON TABLE "public"."transfers" TO "authenticated";
GRANT ALL ON TABLE "public"."transfers" TO "service_role";



GRANT ALL ON SEQUENCE "public"."transfers_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."transfers_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."transfers_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."users" TO "anon";
GRANT ALL ON TABLE "public"."users" TO "authenticated";
GRANT ALL ON TABLE "public"."users" TO "service_role";



GRANT ALL ON SEQUENCE "public"."users_id_seq" TO "anon";
GRANT ALL ON SEQUENCE "public"."users_id_seq" TO "authenticated";
GRANT ALL ON SEQUENCE "public"."users_id_seq" TO "service_role";









ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES TO "service_role";






ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS TO "service_role";






ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES TO "service_role";































