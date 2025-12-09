#!/usr/bin/env python3
import cmd2
import json
import urllib.parse
from .base import BaseCommand
from functions import http_request

# VIDEO API LOCATION
api_destination = "api/video"
#


class VideoCommand(BaseCommand):
    """Video/Conference management commands"""

    def get_parser(self):
        """Create and return the argument parser for video commands"""
        # Create the top level parser for video
        base_parser = cmd2.Cmd2ArgumentParser()
        subparsers = base_parser.add_subparsers(title='VIDEO', help='video help')

        # ==================== ROOM ====================
        room_parser = subparsers.add_parser('room', help='Video room management')
        room_subparsers = room_parser.add_subparsers(title='ROOM', help='room help')

        # room list
        room_list_parser = room_subparsers.add_parser('list', help='List video rooms')
        room_list_parser.add_argument('-i', '--id', help='Get room by ID')
        room_list_parser.add_argument('-n', '--name', help='Get room by unique name')
        room_list_parser.add_argument('-j', '--json', action='store_true', help='Output in JSON format')
        room_list_parser.set_defaults(func='room_list')

        # room create
        room_create_parser = room_subparsers.add_parser('create', help='Create a video room')
        room_create_parser.add_argument('-n', '--name', help='Unique name for the room', required=True)
        room_create_parser.add_argument('--display-name', help='Display name for the room')
        room_create_parser.add_argument('--max-members', type=int, help='Maximum number of members allowed')
        room_create_parser.add_argument('--quality', help='Video quality', choices=['720p', '1080p'])
        room_create_parser.add_argument('--layout', help='Room layout')
        room_create_parser.add_argument('--record-on-start', action='store_true', help='Start recording when room starts')
        room_create_parser.add_argument('--enable-room-previews', action='store_true', help='Enable room previews')
        room_create_parser.set_defaults(func='room_create')

        # room update
        room_update_parser = room_subparsers.add_parser('update', help='Update a video room')
        room_update_parser.add_argument('-i', '--id', help='Room ID to update', required=True)
        room_update_parser.add_argument('-n', '--name', help='New unique name for the room')
        room_update_parser.add_argument('--display-name', help='New display name for the room')
        room_update_parser.add_argument('--max-members', type=int, help='Maximum number of members allowed')
        room_update_parser.add_argument('--quality', help='Video quality', choices=['720p', '1080p'])
        room_update_parser.add_argument('--layout', help='Room layout')
        room_update_parser.add_argument('--record-on-start', action='store_true', help='Start recording when room starts')
        room_update_parser.add_argument('--enable-room-previews', action='store_true', help='Enable room previews')
        room_update_parser.set_defaults(func='room_update')

        # room delete
        room_delete_parser = room_subparsers.add_parser('delete', help='Delete a video room')
        room_delete_parser.add_argument('-i', '--id', help='Room ID to delete', required=True)
        room_delete_parser.add_argument('-f', '--force', action='store_true', help='Force delete without confirmation')
        room_delete_parser.set_defaults(func='room_delete')

        room_parser.set_defaults(func='room_help')

        # ==================== CONFERENCE ====================
        conf_parser = subparsers.add_parser('conference', help='Video conference management')
        conf_subparsers = conf_parser.add_subparsers(title='CONFERENCE', help='conference help')

        # conference list
        conf_list_parser = conf_subparsers.add_parser('list', help='List video conferences')
        conf_list_parser.add_argument('-i', '--id', help='Get conference by ID')
        conf_list_parser.add_argument('-j', '--json', action='store_true', help='Output in JSON format')
        conf_list_parser.set_defaults(func='conference_list')

        # conference create
        conf_create_parser = conf_subparsers.add_parser('create', help='Create a video conference')
        conf_create_parser.add_argument('-n', '--name', help='Name for the conference', required=True)
        conf_create_parser.add_argument('--display-name', help='Display name for the conference')
        conf_create_parser.add_argument('--max-members', type=int, help='Maximum number of members allowed')
        conf_create_parser.add_argument('--quality', help='Video quality', choices=['720p', '1080p'])
        conf_create_parser.add_argument('--layout', help='Conference layout')
        conf_create_parser.add_argument('--record-on-start', action='store_true', help='Start recording when conference starts')
        conf_create_parser.set_defaults(func='conference_create')

        # conference update
        conf_update_parser = conf_subparsers.add_parser('update', help='Update a video conference')
        conf_update_parser.add_argument('-i', '--id', help='Conference ID to update', required=True)
        conf_update_parser.add_argument('-n', '--name', help='New name for the conference')
        conf_update_parser.add_argument('--display-name', help='New display name for the conference')
        conf_update_parser.add_argument('--max-members', type=int, help='Maximum number of members allowed')
        conf_update_parser.add_argument('--quality', help='Video quality', choices=['720p', '1080p'])
        conf_update_parser.add_argument('--layout', help='Conference layout')
        conf_update_parser.set_defaults(func='conference_update')

        # conference delete
        conf_delete_parser = conf_subparsers.add_parser('delete', help='Delete a video conference')
        conf_delete_parser.add_argument('-i', '--id', help='Conference ID to delete', required=True)
        conf_delete_parser.add_argument('-f', '--force', action='store_true', help='Force delete without confirmation')
        conf_delete_parser.set_defaults(func='conference_delete')

        # conference token (nested under conference)
        conf_token_parser = conf_subparsers.add_parser('token', help='Conference token management')
        conf_token_subparsers = conf_token_parser.add_subparsers(title='CONFERENCE TOKEN', help='conference token help')

        # conference token list
        conf_token_list_parser = conf_token_subparsers.add_parser('list', help='List conference tokens')
        conf_token_list_parser.add_argument('--conference-id', help='Conference ID to list tokens for', required=True)
        conf_token_list_parser.add_argument('-j', '--json', action='store_true', help='Output in JSON format')
        conf_token_list_parser.set_defaults(func='conference_token_list')

        # conference token get
        conf_token_get_parser = conf_token_subparsers.add_parser('get', help='Get a conference token by ID')
        conf_token_get_parser.add_argument('-i', '--id', help='Conference token ID', required=True)
        conf_token_get_parser.add_argument('-j', '--json', action='store_true', help='Output in JSON format')
        conf_token_get_parser.set_defaults(func='conference_token_get')

        # conference token reset
        conf_token_reset_parser = conf_token_subparsers.add_parser('reset', help='Reset a conference token')
        conf_token_reset_parser.add_argument('-i', '--id', help='Conference token ID to reset', required=True)
        conf_token_reset_parser.set_defaults(func='conference_token_reset')

        conf_token_parser.set_defaults(func='conference_token_help')

        conf_parser.set_defaults(func='conference_help')

        # ==================== TOKEN ====================
        token_parser = subparsers.add_parser('token', help='Room token management')
        token_subparsers = token_parser.add_subparsers(title='TOKEN', help='token help')

        # token create
        token_create_parser = token_subparsers.add_parser('create', help='Create a room token')
        token_create_parser.add_argument('--room-name', help='Room name to create token for', required=True)
        token_create_parser.add_argument('--user-name', help='User name for the token', required=True)
        token_create_parser.add_argument('--permissions', nargs='+', help='Permissions for the token')
        token_create_parser.add_argument('--auto-create-room', action='store_true', help='Auto-create room if it does not exist')
        token_create_parser.add_argument('--join-from', help='Join from time (ISO 8601)')
        token_create_parser.add_argument('--join-until', help='Join until time (ISO 8601)')
        token_create_parser.add_argument('-j', '--json', action='store_true', help='Output in JSON format')
        token_create_parser.set_defaults(func='token_create')

        token_parser.set_defaults(func='token_help')

        # ==================== SESSION ====================
        session_parser = subparsers.add_parser('session', help='Room session management')
        session_subparsers = session_parser.add_subparsers(title='SESSION', help='session help')

        # session list
        session_list_parser = session_subparsers.add_parser('list', help='List room sessions')
        session_list_parser.add_argument('-i', '--id', help='Get session by ID')
        session_list_parser.add_argument('-j', '--json', action='store_true', help='Output in JSON format')
        session_list_parser.set_defaults(func='session_list')

        # session recordings
        session_recordings_parser = session_subparsers.add_parser('recordings', help='List recordings for a room session')
        session_recordings_parser.add_argument('-i', '--id', help='Room session ID', required=True)
        session_recordings_parser.add_argument('-j', '--json', action='store_true', help='Output in JSON format')
        session_recordings_parser.set_defaults(func='session_recordings')

        # session members
        session_members_parser = session_subparsers.add_parser('members', help='List members for a room session')
        session_members_parser.add_argument('-i', '--id', help='Room session ID', required=True)
        session_members_parser.add_argument('-j', '--json', action='store_true', help='Output in JSON format')
        session_members_parser.set_defaults(func='session_members')

        session_parser.set_defaults(func='session_help')

        # ==================== RECORDING ====================
        recording_parser = subparsers.add_parser('recording', help='Room recording management')
        recording_subparsers = recording_parser.add_subparsers(title='RECORDING', help='recording help')

        # recording list
        recording_list_parser = recording_subparsers.add_parser('list', help='List room recordings')
        recording_list_parser.add_argument('-i', '--id', help='Get recording by ID')
        recording_list_parser.add_argument('-j', '--json', action='store_true', help='Output in JSON format')
        recording_list_parser.set_defaults(func='recording_list')

        # recording delete
        recording_delete_parser = recording_subparsers.add_parser('delete', help='Delete a room recording')
        recording_delete_parser.add_argument('-i', '--id', help='Recording ID to delete', required=True)
        recording_delete_parser.add_argument('-f', '--force', action='store_true', help='Force delete without confirmation')
        recording_delete_parser.set_defaults(func='recording_delete')

        recording_parser.set_defaults(func='recording_help')

        # ==================== STREAM ====================
        stream_parser = subparsers.add_parser('stream', help='Stream management')
        stream_subparsers = stream_parser.add_subparsers(title='STREAM', help='stream help')

        # stream list
        stream_list_parser = stream_subparsers.add_parser('list', help='List streams')
        stream_list_group = stream_list_parser.add_mutually_exclusive_group(required=True)
        stream_list_group.add_argument('-i', '--id', help='Get stream by ID')
        stream_list_group.add_argument('--room-id', help='List streams by room ID')
        stream_list_group.add_argument('--conference-id', help='List streams by conference ID')
        stream_list_parser.add_argument('-j', '--json', action='store_true', help='Output in JSON format')
        stream_list_parser.set_defaults(func='stream_list')

        # stream create
        stream_create_parser = stream_subparsers.add_parser('create', help='Create a stream')
        stream_create_group = stream_create_parser.add_mutually_exclusive_group(required=True)
        stream_create_group.add_argument('--room-id', help='Room ID to create stream for')
        stream_create_group.add_argument('--conference-id', help='Conference ID to create stream for')
        stream_create_parser.add_argument('--url', help='Stream URL (RTMP endpoint)', required=True)
        stream_create_parser.set_defaults(func='stream_create')

        # stream update
        stream_update_parser = stream_subparsers.add_parser('update', help='Update a stream')
        stream_update_parser.add_argument('-i', '--id', help='Stream ID to update', required=True)
        stream_update_parser.add_argument('--url', help='New stream URL')
        stream_update_parser.set_defaults(func='stream_update')

        # stream delete
        stream_delete_parser = stream_subparsers.add_parser('delete', help='Delete a stream')
        stream_delete_parser.add_argument('-i', '--id', help='Stream ID to delete', required=True)
        stream_delete_parser.add_argument('-f', '--force', action='store_true', help='Force delete without confirmation')
        stream_delete_parser.set_defaults(func='stream_delete')

        stream_parser.set_defaults(func='stream_help')

        return base_parser

    def handle_command(self, args):
        """
        Handle video command routing
        """
        # Process environment variables once for all commands
        args = self.is_env_var(args)

        func_name = getattr(args, 'func', None)
        if func_name is not None:
            getattr(self, func_name)(args)
        else:
            self.shell.do_help('video')

    # ==================== HELP FUNCTIONS ====================
    def room_help(self, args):
        """Show room subcommand help"""
        print("Usage: video room {list,create,update,delete} [options]")
        print("\nRoom subcommands:")
        print("  list     List video rooms")
        print("  create   Create a video room")
        print("  update   Update a video room")
        print("  delete   Delete a video room")
        print("\nUse 'video room <subcommand> -h' for more information.\n")

    def conference_help(self, args):
        """Show conference subcommand help"""
        print("Usage: video conference {list,create,update,delete,token} [options]")
        print("\nConference subcommands:")
        print("  list     List video conferences")
        print("  create   Create a video conference")
        print("  update   Update a video conference")
        print("  delete   Delete a video conference")
        print("  token    Conference token management")
        print("\nUse 'video conference <subcommand> -h' for more information.\n")

    def token_help(self, args):
        """Show token subcommand help"""
        print("Usage: video token {create} [options]")
        print("\nToken subcommands:")
        print("  create   Create a room token")
        print("\nUse 'video token <subcommand> -h' for more information.\n")

    def session_help(self, args):
        """Show session subcommand help"""
        print("Usage: video session {list,recordings,members} [options]")
        print("\nSession subcommands:")
        print("  list        List room sessions")
        print("  recordings  List recordings for a room session")
        print("  members     List members for a room session")
        print("\nUse 'video session <subcommand> -h' for more information.\n")

    def recording_help(self, args):
        """Show recording subcommand help"""
        print("Usage: video recording {list,delete} [options]")
        print("\nRecording subcommands:")
        print("  list     List room recordings")
        print("  delete   Delete a room recording")
        print("\nUse 'video recording <subcommand> -h' for more information.\n")

    def stream_help(self, args):
        """Show stream subcommand help"""
        print("Usage: video stream {list,create,update,delete} [options]")
        print("\nStream subcommands:")
        print("  list     List streams")
        print("  create   Create a stream")
        print("  update   Update a stream")
        print("  delete   Delete a stream")
        print("\nUse 'video stream <subcommand> -h' for more information.\n")

    def conference_token_help(self, args):
        """Show conference token subcommand help"""
        print("Usage: video conference token {list,get,reset} [options]")
        print("\nConference token subcommands:")
        print("  list     List conference tokens")
        print("  get      Get a conference token by ID")
        print("  reset    Reset a conference token")
        print("\nUse 'video conference token <subcommand> -h' for more information.\n")

    # ==================== ROOMS ====================
    def room_list(self, args):
        """List video rooms"""
        if args.id:
            query_params = f"/rooms/{args.id}"
        elif args.name:
            query_params = f"/rooms/{urllib.parse.quote(args.name)}"
        else:
            query_params = "/rooms"

        output, status_code = self._video_func(query_params, req_type="GET")
        valid = self.handle_standard_response(output, status_code)

        if valid:
            self.display_output(output, json_format=args.json)

    def room_create(self, args):
        """Create a video room"""
        payload = self._build_room_payload(args)

        output, status_code = self._video_func("/rooms", req_type="POST", payload=json.dumps(payload))
        valid = self.handle_standard_response(output, status_code)

        if valid:
            output_json = json.loads(output)
            room_id = output_json.get("id", "unknown")
            room_name = output_json.get("name", args.name)
            print(f"Success! Room '{room_name}' created with ID: {room_id}\n")

    def room_update(self, args):
        """Update a video room"""
        if not args.id:
            print("Room ID is required to update a room\n")
            return

        payload = self._build_room_payload(args)
        if not payload:
            print("At least one parameter is required to update a room\n")
            return

        query_params = f"/rooms/{args.id}"
        output, status_code = self._video_func(query_params, req_type="PUT", payload=json.dumps(payload))
        valid = self.handle_standard_response(output, status_code)

        if valid:
            print(f"Complete. Room {args.id} has been updated.\n")

    def room_delete(self, args):
        """Delete a video room"""
        if not args.id:
            print("Room ID is required for deletion\n")
            return

        if self.confirm_deletion("Room", args.id, args.force):
            query_params = f"/rooms/{args.id}"
            output, status_code = self._video_func(query_params, req_type="DELETE")

            if status_code == 204:
                print(f"Success! Room {args.id} has been deleted\n")
            else:
                valid = self.handle_standard_response(output, status_code)
                if not valid:
                    print(f"Error deleting room: {output}")
        else:
            print("Delete operation cancelled\n")

    def _build_room_payload(self, args):
        """Build payload for room create/update"""
        payload = {}
        if hasattr(args, 'name') and args.name:
            payload['name'] = args.name
        if hasattr(args, 'display_name') and args.display_name:
            payload['display_name'] = args.display_name
        if hasattr(args, 'max_members') and args.max_members:
            payload['max_members'] = args.max_members
        if hasattr(args, 'quality') and args.quality:
            payload['quality'] = args.quality
        if hasattr(args, 'layout') and args.layout:
            payload['layout'] = args.layout
        if hasattr(args, 'record_on_start') and args.record_on_start:
            payload['record_on_start'] = True
        if hasattr(args, 'enable_room_previews') and args.enable_room_previews:
            payload['enable_room_previews'] = True
        return payload

    # ==================== CONFERENCES ====================
    def conference_list(self, args):
        """List video conferences"""
        if args.id:
            query_params = f"/conferences/{args.id}"
        else:
            query_params = "/conferences"

        output, status_code = self._video_func(query_params, req_type="GET")
        valid = self.handle_standard_response(output, status_code)

        if valid:
            self.display_output(output, json_format=args.json)

    def conference_create(self, args):
        """Create a video conference"""
        payload = self._build_conference_payload(args)

        output, status_code = self._video_func("/conferences", req_type="POST", payload=json.dumps(payload))
        valid = self.handle_standard_response(output, status_code)

        if valid:
            output_json = json.loads(output)
            conf_id = output_json.get("id", "unknown")
            conf_name = output_json.get("name", args.name)
            print(f"Success! Conference '{conf_name}' created with ID: {conf_id}\n")

    def conference_update(self, args):
        """Update a video conference"""
        if not args.id:
            print("Conference ID is required to update a conference\n")
            return

        payload = self._build_conference_payload(args)
        if not payload:
            print("At least one parameter is required to update a conference\n")
            return

        query_params = f"/conferences/{args.id}"
        output, status_code = self._video_func(query_params, req_type="PUT", payload=json.dumps(payload))
        valid = self.handle_standard_response(output, status_code)

        if valid:
            print(f"Complete. Conference {args.id} has been updated.\n")

    def conference_delete(self, args):
        """Delete a video conference"""
        if not args.id:
            print("Conference ID is required for deletion\n")
            return

        if self.confirm_deletion("Conference", args.id, args.force):
            query_params = f"/conferences/{args.id}"
            output, status_code = self._video_func(query_params, req_type="DELETE")

            if status_code == 204:
                print(f"Success! Conference {args.id} has been deleted\n")
            else:
                valid = self.handle_standard_response(output, status_code)
                if not valid:
                    print(f"Error deleting conference: {output}")
        else:
            print("Delete operation cancelled\n")

    def _build_conference_payload(self, args):
        """Build payload for conference create/update"""
        payload = {}
        if hasattr(args, 'name') and args.name:
            payload['name'] = args.name
        if hasattr(args, 'display_name') and args.display_name:
            payload['display_name'] = args.display_name
        if hasattr(args, 'max_members') and args.max_members:
            payload['max_members'] = args.max_members
        if hasattr(args, 'quality') and args.quality:
            payload['quality'] = args.quality
        if hasattr(args, 'layout') and args.layout:
            payload['layout'] = args.layout
        if hasattr(args, 'record_on_start') and args.record_on_start:
            payload['record_on_start'] = True
        return payload

    # ==================== ROOM TOKENS ====================
    def token_create(self, args):
        """Create a room token"""
        payload = {
            'room_name': args.room_name,
            'user_name': args.user_name
        }

        if args.permissions:
            payload['permissions'] = args.permissions
        if args.auto_create_room:
            payload['auto_create_room'] = True
        if args.join_from:
            payload['join_from'] = args.join_from
        if args.join_until:
            payload['join_until'] = args.join_until

        output, status_code = self._video_func("/room_tokens", req_type="POST", payload=json.dumps(payload))
        valid = self.handle_standard_response(output, status_code)

        if valid:
            if args.json:
                self.display_output(output, json_format=True)
            else:
                output_json = json.loads(output)
                token = output_json.get("token", "")
                print(f"Room token created successfully!\n")
                print(f"Token: {token}\n")

    # ==================== ROOM SESSIONS ====================
    def session_list(self, args):
        """List room sessions"""
        if args.id:
            query_params = f"/room_sessions/{args.id}"
        else:
            query_params = "/room_sessions"

        output, status_code = self._video_func(query_params, req_type="GET")
        valid = self.handle_standard_response(output, status_code)

        if valid:
            self.display_output(output, json_format=args.json)

    def session_recordings(self, args):
        """List recordings for a room session"""
        if not args.id:
            print("Room session ID is required\n")
            return

        query_params = f"/room_sessions/{args.id}/recordings"
        output, status_code = self._video_func(query_params, req_type="GET")
        valid = self.handle_standard_response(output, status_code)

        if valid:
            self.display_output(output, json_format=args.json)

    def session_members(self, args):
        """List members for a room session"""
        if not args.id:
            print("Room session ID is required\n")
            return

        query_params = f"/room_sessions/{args.id}/members"
        output, status_code = self._video_func(query_params, req_type="GET")
        valid = self.handle_standard_response(output, status_code)

        if valid:
            self.display_output(output, json_format=args.json)

    # ==================== ROOM RECORDINGS ====================
    def recording_list(self, args):
        """List room recordings"""
        if args.id:
            query_params = f"/room_recordings/{args.id}"
        else:
            query_params = "/room_recordings"

        output, status_code = self._video_func(query_params, req_type="GET")
        valid = self.handle_standard_response(output, status_code)

        if valid:
            self.display_output(output, json_format=args.json)

    def recording_delete(self, args):
        """Delete a room recording"""
        if not args.id:
            print("Recording ID is required for deletion\n")
            return

        if self.confirm_deletion("Recording", args.id, args.force):
            query_params = f"/room_recordings/{args.id}"
            output, status_code = self._video_func(query_params, req_type="DELETE")

            if status_code == 204:
                print(f"Success! Recording {args.id} has been deleted\n")
            else:
                valid = self.handle_standard_response(output, status_code)
                if not valid:
                    print(f"Error deleting recording: {output}")
        else:
            print("Delete operation cancelled\n")

    # ==================== STREAMS ====================
    def stream_list(self, args):
        """List streams"""
        if args.id:
            query_params = f"/streams/{args.id}"
        elif args.room_id:
            query_params = f"/rooms/{args.room_id}/streams"
        elif args.conference_id:
            query_params = f"/conferences/{args.conference_id}/streams"
        else:
            print("Either --id, --room-id, or --conference-id is required\n")
            return

        output, status_code = self._video_func(query_params, req_type="GET")
        valid = self.handle_standard_response(output, status_code)

        if valid:
            self.display_output(output, json_format=args.json)

    def stream_create(self, args):
        """Create a stream"""
        payload = {'url': args.url}

        if args.room_id:
            query_params = f"/rooms/{args.room_id}/streams"
        else:
            query_params = f"/conferences/{args.conference_id}/streams"

        output, status_code = self._video_func(query_params, req_type="POST", payload=json.dumps(payload))
        valid = self.handle_standard_response(output, status_code)

        if valid:
            output_json = json.loads(output)
            stream_id = output_json.get("id", "unknown")
            print(f"Success! Stream created with ID: {stream_id}\n")

    def stream_update(self, args):
        """Update a stream"""
        if not args.id:
            print("Stream ID is required to update a stream\n")
            return

        payload = {}
        if args.url:
            payload['url'] = args.url

        if not payload:
            print("At least one parameter is required to update a stream\n")
            return

        query_params = f"/streams/{args.id}"
        output, status_code = self._video_func(query_params, req_type="PUT", payload=json.dumps(payload))
        valid = self.handle_standard_response(output, status_code)

        if valid:
            print(f"Complete. Stream {args.id} has been updated.\n")

    def stream_delete(self, args):
        """Delete a stream"""
        if not args.id:
            print("Stream ID is required for deletion\n")
            return

        if self.confirm_deletion("Stream", args.id, args.force):
            query_params = f"/streams/{args.id}"
            output, status_code = self._video_func(query_params, req_type="DELETE")

            if status_code == 204:
                print(f"Success! Stream {args.id} has been deleted\n")
            else:
                valid = self.handle_standard_response(output, status_code)
                if not valid:
                    print(f"Error deleting stream: {output}")
        else:
            print("Delete operation cancelled\n")

    # ==================== CONFERENCE TOKENS ====================
    def conference_token_list(self, args):
        """List conference tokens"""
        if not args.conference_id:
            print("Conference ID is required\n")
            return

        query_params = f"/conferences/{args.conference_id}/conference_tokens"
        output, status_code = self._video_func(query_params, req_type="GET")
        valid = self.handle_standard_response(output, status_code)

        if valid:
            self.display_output(output, json_format=args.json)

    def conference_token_get(self, args):
        """Get a conference token by ID"""
        if not args.id:
            print("Conference token ID is required\n")
            return

        query_params = f"/conference_tokens/{args.id}"
        output, status_code = self._video_func(query_params, req_type="GET")
        valid = self.handle_standard_response(output, status_code)

        if valid:
            self.display_output(output, json_format=args.json)

    def conference_token_reset(self, args):
        """Reset a conference token"""
        if not args.id:
            print("Conference token ID is required\n")
            return

        query_params = f"/conference_tokens/{args.id}/reset"
        output, status_code = self._video_func(query_params, req_type="POST")
        valid = self.handle_standard_response(output, status_code)

        if valid:
            print(f"Success! Conference token {args.id} has been reset\n")

    # ==================== HELPER METHODS ====================
    def _video_func(self, query_params="", req_type="GET", payload={}):
        """Make HTTP request to video API"""
        destination = f"{api_destination}{query_params}"
        response = http_request(destination, req_type, payload)
        return (response.text, response.status_code)
